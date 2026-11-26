"""用 Stable Baselines3 的 PPO 訓練自動駕駛。

PPO（Proximal Policy Optimization, Schulman et al., 2017）+ GAE（Schulman et al., 2015），
都是 2022 年以前發表的方法。執行入口：scripts/train_cpu.py 和 scripts/train_gpu.py。

存檔位置（預設 models/ppo/）：
    best_model.zip                    評估時存活最久的模型
    last_model.zip + last_progress.json   最新的模型和目前回合數（--resume 用）
    checkpoints/ppo_ep{N}.zip         第 N 回合時的模型（--save-episodes 指定）
"""
import argparse
import json
import os
import time
from collections import OrderedDict, deque
from pathlib import Path

import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecMonitor

from ..paths import MODELS_DIR
from .env import MAX_STEPS, ShmupEnv

EVAL_SEED = 100000                 # 評估固定用 seed 100000、100001 …，不同模型才能公平比較

DEFAULTS = OrderedDict([
    ("device", "cpu"),
    ("n_envs", os.cpu_count() or 4),   # 同時玩幾局；每一局一個程序，預設 = CPU 核心數
    ("max_episodes", 2000),            # 玩滿這麼多回合就停（0 = 只看 total_steps）
    ("save_episodes", "10,50,500,2000"),
    ("total_steps", 50000000),         # 安全上限，通常會先因為 max_episodes 停下來
    ("n_steps", 1024),                 # 每個環境每次收集幾步再更新（rollout 長度）
    ("batch_size", 256),
    ("n_epochs", 10),                  # 每批資料重複學幾輪
    ("lr", 2.5e-4),
    ("gamma", 0.99),
    ("gae_lambda", 0.95),
    ("clip_range", 0.2),
    ("ent_coef", 0.01),                # 鼓勵探索：讓動作分布不要太快變成只選一個
    ("vf_coef", 0.5),
    ("max_grad_norm", 0.5),
    ("hidden", 256),                   # 策略網路和價值網路各兩層、每層幾個單元
    ("eval_every", 200000),            # 每幾步評估一次並更新 best_model
    ("eval_episodes", 5),
    ("milestone_eval", 5),             # 存里程碑時順便評估幾局
    ("seed", 1),
    ("threads", 2),                    # torch 用幾個 CPU 執行緒（這個網路很小，2 個最快）
    ("out_dir", str(MODELS_DIR / "ppo")),
    ("resume", ""),                    # 要接著訓練的模型，例如 models/ppo/last_model.zip
])


def build_arg_parser(description, overrides):
    """每個超參數都變成命令列參數；`overrides` 用來改預設值。"""
    cfg = OrderedDict(DEFAULTS)
    cfg.update(overrides)
    ap = argparse.ArgumentParser(description=description,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    for key, value in cfg.items():
        ap.add_argument("--" + key.replace("_", "-"), type=type(value), default=value)
    ap.add_argument("--eval-only", default="", metavar="MODEL",
                    help="不訓練，只評估這個模型檔（例如 models/ppo/best_model.zip）")
    return ap


# ---------------------------------------------------------------------------
# 評估
# ---------------------------------------------------------------------------
def evaluate(model, episodes=5, seed=EVAL_SEED, max_steps=MAX_STEPS):
    """用固定的 seed、選機率最高的動作（不隨機）玩幾局。"""
    env = ShmupEnv(max_steps)
    lengths, scores, stages, clears = [], [], [], 0
    for i in range(episodes):
        obs, _ = env.reset(seed=seed + i)
        while True:
            action, _ = model.predict(obs, deterministic=True)
            obs, _, term, trunc, info = env.step(int(action))
            if term or trunc:
                break
        lengths.append(info["t"])
        scores.append(info["score"])
        stages.append(info["stage"])
        clears += 1 if info["cleared"] else 0
    return {"survival": float(np.mean(lengths)), "seconds": float(np.mean(lengths)) / 30.0,
            "score": float(np.mean(scores)), "stage": float(np.mean(stages)), "clears": clears,
            "episodes": episodes}


def format_eval(s):
    return ("存活 %.0f 步（%.1f 秒）  分數 %.0f  平均第 %.2f 關  ALL CLEAR %d/%d"
            % (s["survival"], s["seconds"], s["score"], s["stage"], s["clears"], s["episodes"]))


# ---------------------------------------------------------------------------
# 訓練過程的 callback：數回合、印 log、存里程碑、評估、提早停止
# ---------------------------------------------------------------------------
class ProgressCallback(BaseCallback):
    def __init__(self, cfg, start_episodes=0, best=-1.0):
        super(ProgressCallback, self).__init__()
        self.cfg = cfg
        self.out = Path(cfg["out_dir"])
        self.episodes = start_episodes
        self.best = best
        self.recent = deque(maxlen=50)
        wanted = sorted(int(x) for x in str(cfg["save_episodes"]).split(",") if x.strip())
        self.milestones = [m for m in wanted if m > start_episodes]
        self.start_time = time.time()
        self.start_steps = 0
        self.next_eval = 0

    def _on_training_start(self):
        self.start_steps = self.num_timesteps
        every = self.cfg["eval_every"]
        self.next_eval = (self.num_timesteps // every + 1) * every

    def _on_step(self):
        for info in self.locals["infos"]:
            ep = info.get("episode")
            if ep is not None:
                self.episodes += 1
                self.recent.append((ep["r"], ep["l"], info.get("stage", 1), info.get("cleared", False)))
                while self.milestones and self.episodes >= self.milestones[0]:
                    self._save_milestone(self.milestones.pop(0))
        if self.num_timesteps >= self.next_eval:
            self.next_eval += self.cfg["eval_every"]
            self._evaluate()
        if self.cfg["max_episodes"] and self.episodes >= self.cfg["max_episodes"]:
            print("已經玩滿 %d 回合，停止訓練。" % self.cfg["max_episodes"], flush=True)
            return False
        return True

    def _on_rollout_end(self):
        if not self.recent:
            return
        r = np.array([x[0] for x in self.recent])
        length = np.array([x[1] for x in self.recent])
        stage = np.array([x[2] for x in self.recent])
        clears = sum(1 for x in self.recent if x[3])
        elapsed = time.time() - self.start_time
        fps = (self.num_timesteps - self.start_steps) / max(elapsed, 1e-9)
        print("step %10d  ep %5d | return %7.2f  length %6.0f  stage %.2f  clear %2d/%d | "
              "%5.0f steps/s | %6.0fs"
              % (self.num_timesteps, self.episodes, r.mean(), length.mean(), stage.mean(),
                 clears, len(self.recent), fps, elapsed), flush=True)

    def _save_milestone(self, m):
        path = self.out / "checkpoints" / ("ppo_ep%d.zip" % m)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.model.save(str(path))
        stats = evaluate(self.model, self.cfg["milestone_eval"])
        print("  [第 %d 回合] 存檔 %s | %s" % (m, path, format_eval(stats)), flush=True)

    def _evaluate(self):
        stats = evaluate(self.model, self.cfg["eval_episodes"])
        print("  eval：%s" % format_eval(stats), flush=True)
        if stats["survival"] > self.best:
            self.best = stats["survival"]
            self.model.save(str(self.out / "best_model.zip"))
            print("  新的最佳模型 -> %s" % (self.out / "best_model.zip"), flush=True)
        self.save_last()

    def save_last(self):
        self.out.mkdir(parents=True, exist_ok=True)
        self.model.save(str(self.out / "last_model.zip"))
        with open(str(self.out / "last_progress.json"), "w") as f:
            json.dump({"episodes": self.episodes, "steps": int(self.num_timesteps),
                       "best": self.best}, f)


# ---------------------------------------------------------------------------
# 訓練
# ---------------------------------------------------------------------------
def make_env(rank, seed):
    def _init():
        env = ShmupEnv()
        env.reset(seed=seed * 10007 + rank)
        return env
    return _init


def train(cfg):
    if cfg["threads"] > 0:
        torch.set_num_threads(cfg["threads"])
    out = Path(cfg["out_dir"])
    out.mkdir(parents=True, exist_ok=True)
    n = cfg["n_envs"]
    fns = [make_env(i, cfg["seed"]) for i in range(n)]
    venv = SubprocVecEnv(fns, start_method="spawn") if n > 1 else DummyVecEnv(fns)
    venv = VecMonitor(venv)
    venv.seed(cfg["seed"])

    start_episodes, best = 0, -1.0
    if cfg["resume"]:
        model = PPO.load(cfg["resume"], env=venv, device=cfg["device"])
        progress = Path(cfg["resume"]).with_name("last_progress.json")
        if progress.exists():
            saved = json.loads(progress.read_text())
            start_episodes, best = saved.get("episodes", 0), saved.get("best", -1.0)
        print("從 %s 接著訓練（第 %d 步、第 %d 回合）"
              % (cfg["resume"], model.num_timesteps, start_episodes))
    else:
        h = cfg["hidden"]
        model = PPO(
            "MlpPolicy", venv,
            n_steps=cfg["n_steps"], batch_size=cfg["batch_size"], n_epochs=cfg["n_epochs"],
            learning_rate=cfg["lr"], gamma=cfg["gamma"], gae_lambda=cfg["gae_lambda"],
            clip_range=cfg["clip_range"], ent_coef=cfg["ent_coef"], vf_coef=cfg["vf_coef"],
            max_grad_norm=cfg["max_grad_norm"],
            policy_kwargs=dict(net_arch=dict(pi=[h, h], vf=[h, h])),
            seed=cfg["seed"], device=cfg["device"], verbose=0)

    n_params = sum(p.numel() for p in model.policy.parameters())
    print("PPO  device=%s  同時 %d 局（%d 個程序）  參數 %d 個" % (model.device, n, n, n_params))
    print(json.dumps(cfg, ensure_ascii=False))

    cb = ProgressCallback(cfg, start_episodes, best)
    try:
        model.learn(total_timesteps=cfg["total_steps"], callback=cb,
                    reset_num_timesteps=not cfg["resume"])
    except KeyboardInterrupt:
        print("訓練被中斷。")
    finally:
        cb.save_last()
        venv.close()
    if not (out / "best_model.zip").exists():
        model.save(str(out / "best_model.zip"))
    elapsed = (time.time() - cb.start_time) / 60
    print("共 %d 步、%d 回合，花了 %.1f 分鐘。最新模型：%s"
          % (model.num_timesteps, cb.episodes, elapsed, out / "last_model.zip"))
    print("匯出給網頁版：python scripts/export_web.py")
    return model


def run(cfg, eval_only=""):
    if eval_only:
        model = PPO.load(eval_only, device="cpu")
        print(format_eval(evaluate(model, 10)))
    else:
        train(cfg)
