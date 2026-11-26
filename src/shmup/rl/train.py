"""用 Stable Baselines3（1.6.2）的 PPO 訓練自動駕駛。

PPO（Schulman et al., 2017）+ GAE（Schulman et al., 2015），都是 2022 年以前的方法。

    python -m shmup train                         # 有 GPU 就用 GPU 設定，玩到 2000 回合
    python -m shmup train --device cpu            # 強制用 CPU 設定
    python -m shmup train --resume auto           # 有上次的存檔就接著訓練（Colab 斷線後用）

一次訓練的輸出（預設 models/ppo/）：
    config.json / versions.json        這次用的超參數、套件版本（之後才知道怎麼重現）
    part1.monitor.csv …                每一回合的總獎勵、長度、關卡（畫學習曲線用）
    best_model.zip                     評估時存活最久的模型
    last_model.zip / last_progress.json  最新的模型和目前回合數（續訓用）
    checkpoints/ppo_ep{N}.zip          第 N 回合時的模型（錄影、報告用）
"""
import json
import os
import platform
import time
from collections import deque
from pathlib import Path

import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecMonitor

from ..paths import MODELS_DIR
from .env import ShmupEnv
from .evaluate import evaluate, format_eval, model_actor

# 所有超參數；命令列的 --xxx 會蓋掉這裡的值。None 表示「依 CPU / GPU 設定決定」。
DEFAULTS = {
    "device": "auto",                  # auto：有 CUDA 就用 GPU 設定
    "n_envs": os.cpu_count() or 4,     # 同時玩幾局；每一局一個程序，預設 = CPU 核心數
    "max_episodes": 2000,              # 玩滿這麼多回合就停（0 = 只看 total_steps）
    "save_episodes": "10,50,500,2000",
    "total_steps": 50000000,           # 安全上限，通常會先因為 max_episodes 停下來
    "n_steps": None,                   # 每個環境每次收集幾步再更新（CPU 1024 / GPU 2048）
    "batch_size": None,                # CPU 256 / GPU 1024
    "hidden": None,                    # 策略網路、價值網路每層幾個單元（CPU 256 / GPU 512）
    "n_epochs": 10,
    "lr": 2.5e-4,
    "gamma": 0.99,
    "gae_lambda": 0.95,
    "clip_range": 0.2,
    "ent_coef": 0.01,
    "vf_coef": 0.5,
    "max_grad_norm": 0.5,
    "eval_every": 200000,              # 每幾步評估一次並更新 best_model
    "eval_episodes": 5,
    "milestone_eval": 5,
    "seed": 1,
    "threads": 2,                      # torch 用幾個 CPU 執行緒
    "out_dir": str(MODELS_DIR / "ppo"),
    "resume": "",                      # 模型路徑，或 "auto"（有 last_model.zip 就接著訓練）
}
PROFILES = {
    "cpu": {"n_steps": 1024, "batch_size": 256, "hidden": 256},
    "cuda": {"n_steps": 2048, "batch_size": 1024, "hidden": 512},
}


def resolve(cfg):
    """把 auto / None 換成實際的值。"""
    cfg = dict(cfg)
    if cfg["device"] == "auto":
        cfg["device"] = "cuda" if torch.cuda.is_available() else "cpu"
    profile = PROFILES["cuda" if cfg["device"].startswith("cuda") else "cpu"]
    for key, value in profile.items():
        if cfg.get(key) is None:
            cfg[key] = value
    out = Path(cfg["out_dir"])
    if cfg["resume"] == "auto":
        cfg["resume"] = str(out / "last_model.zip") if (out / "last_model.zip").exists() else ""
    return cfg


def versions():
    import gym
    import stable_baselines3
    return {"python": platform.python_version(), "torch": torch.__version__,
            "stable_baselines3": stable_baselines3.__version__, "gym": gym.__version__,
            "numpy": np.__version__, "cuda": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}


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
        stats = evaluate(model_actor(self.model), self.cfg["milestone_eval"])
        print("  [第 %d 回合] 存檔 %s | %s" % (m, path, format_eval(stats)), flush=True)

    def _evaluate(self):
        stats = evaluate(model_actor(self.model), self.cfg["eval_episodes"])
        print("  eval：%s" % format_eval(stats), flush=True)
        if stats["survival"] > self.best:
            self.best = stats["survival"]
            self.model.save(str(self.out / "best_model.zip"))
            print("  新的最佳模型 -> %s" % (self.out / "best_model.zip"), flush=True)
        self.save_last()

    def save_last(self):
        self.model.save(str(self.out / "last_model.zip"))
        (self.out / "last_progress.json").write_text(json.dumps(
            {"episodes": self.episodes, "steps": int(self.num_timesteps), "best": self.best}))


# ---------------------------------------------------------------------------
# 訓練
# ---------------------------------------------------------------------------
def make_env():
    return ShmupEnv()


def train(cfg):
    cfg = resolve(cfg)
    if cfg["threads"] > 0:
        torch.set_num_threads(cfg["threads"])
    out = Path(cfg["out_dir"])
    out.mkdir(parents=True, exist_ok=True)

    n = cfg["n_envs"]
    venv = SubprocVecEnv([make_env] * n, start_method="spawn") if n > 1 else DummyVecEnv([make_env])
    part = len(list(out.glob("part*.monitor.csv"))) + 1          # 續訓時不覆蓋之前的紀錄
    venv = VecMonitor(venv, filename=str(out / ("part%d.monitor.csv" % part)),
                      info_keywords=("stage", "cleared"))
    venv.seed(cfg["seed"] * 1000 + part)

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
            policy_kwargs=dict(net_arch=[dict(pi=[h, h], vf=[h, h])]),
            seed=cfg["seed"], device=cfg["device"], verbose=0)

    (out / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
    (out / "versions.json").write_text(json.dumps(versions(), indent=2))
    n_params = sum(p.numel() for p in model.policy.parameters())
    print("PPO  device=%s  同時 %d 局（%d 個程序）  參數 %d 個" % (model.device, n, n, n_params))
    print(json.dumps(versions()))

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
    print("共 %d 步、%d 回合，花了 %.1f 分鐘。"
          % (model.num_timesteps, cb.episodes, (time.time() - cb.start_time) / 60))
    print("下一步：python -m shmup report   （學習曲線 + 結果表）")
    return model
