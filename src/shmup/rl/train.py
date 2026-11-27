"""用 Stable Baselines3（1.5.0）的 PPO 訓練自動駕駛。

PPO（Schulman et al., 2017）+ GAE（Schulman et al., 2015），都是 2022 年以前的方法。

    python -m shmup train                         # 有 GPU 就用 GPU 設定，玩到 5000 回合
    python -m shmup train --device cpu            # 強制用 CPU 設定
    python -m shmup train --resume auto           # 有上次的存檔就接著訓練（Colab 斷線後用）

一次訓練的輸出（預設 models/ppo/）：
    config.json / versions.json        這次用的超參數、套件版本（之後才知道怎麼重現）
    part1.monitor.csv …                每一回合的總獎勵、長度、關卡（畫學習曲線用）
    best_model.zip                     評估（另一組 seed）時通關最多的模型
    train_stats.csv                    每次更新的 approx_kl、clip_fraction、entropy、學習率…（看訓練穩不穩）
    last_model.zip / last_progress.json  最新的模型和目前回合數（續訓用）
    checkpoints/ppo_ep{N}.zip          第 N 回合時的模型（報告、網頁選單用）
    milestones.json / best.json        每個里程碑和最佳模型的紀錄（時間、步數、評估結果）
    web/                               自動匯出的網頁版模型（同時也寫進專案的 web/model/）
"""
import csv
import datetime
import math
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

from ..paths import MODELS_DIR, WEB_DIR
from .env import ShmupEnv
from .evaluate import SELECT_SEED, evaluate, format_eval, model_actor
from .features import OBS_DIM
from .policy import compatible, export_run, model_obs_dim

# 所有超參數；命令列的 --xxx 會蓋掉這裡的值。None 表示「依 CPU / GPU 設定決定」。
DEFAULTS = {
    "device": "auto",                  # auto：有 CUDA 就用 GPU 設定
    "n_envs": os.cpu_count() or 4,     # 同時玩幾局；每一局一個程序，預設 = CPU 核心數
    "max_episodes": 5000,              # 玩滿這麼多回合就停（0 = 只看 total_steps）
    "save_episodes": "100,500,2000,5000",
    "total_steps": 300000000,          # 安全上限，通常會先因為 max_episodes 停下來
    "n_steps": None,                   # 每個環境每次收集幾步再更新（None = 總共 8192 / 16384 步平均分給每局）
    "batch_size": None,                # CPU 256 / GPU 1024
    "pi_layers": "256,256",            # 策略網路每層的單元數
    "vf_layers": "512,512",            # 價值網路每層的單元數（價值比較難估，給大一點）
    "n_epochs": 10,
    "gamma": 0.99,
    "gae_lambda": 0.95,
    "vf_coef": 0.5,
    "max_grad_norm": 0.5,
    # 下面三個在 anneal_start 步之前用 *_start，到 anneal_end 步時降到 *_end（中間平滑地降）。
    # 前期學得快，後期每次更新變小，策略才不會一直來回晃。
    "lr": 2.5e-4,
    "lr_end": 2.5e-5,
    "clip_range": 0.2,
    "clip_end": 0.1,
    "ent_coef": 0.01,
    "ent_end": 0.002,
    "anneal_start": 5000000,
    "anneal_end": 20000000,
    "target_kl": 0.02,                 # 一次更新內 KL 超過 1.5 倍就提早停（0 = 不限制）
    "eval_every": 1000000,             # 每幾步評估一次並更新 best_model（後期一局很長，評估要花時間）
    "eval_episodes": 20,               # 選 best_model 用的局數（seed 200000 起，跟報告的局不重疊）
    "milestone_eval": 10,              # 里程碑模型的評估局數（seed 100000 起，跟報告同一組）
    "seed": 1,
    "threads": 2,                      # torch 用幾個 CPU 執行緒
    "out_dir": str(MODELS_DIR / "ppo"),
    "resume": "",                      # 模型路徑，或 "auto"（有 last_model.zip 就接著訓練）
}
# rollout = 每次更新前，所有環境加起來收集的步數。用「總數」來設定，
# 同時玩的局數變多時，每局收集的步數就自動變少，學習速度（每回合學到的東西）才不會變慢。
PROFILES = {
    "cpu": {"rollout": 8192, "batch_size": 256},
    "cuda": {"rollout": 16384, "batch_size": 1024},
}


def gpu_supported():
    """這版 torch（2022 年 3 月的 1.11）有沒有這張 GPU 能跑的程式碼。

    CUDA 的規則：sm_XY 編譯的程式可以在 X 相同、小版本 >= Y 的 GPU 上跑（T4 是 7.5，可以跑 sm_70）；
    compute_XY（PTX）可以在 >= XY 的 GPU 上即時編譯。L4（8.9）、A100（8.0）這些比較新的 GPU 都不在
    PyPI 版 torch 1.11.0 的清單裡，硬跑會出現「no kernel image is available」。
    """
    try:
        major, minor = torch.cuda.get_device_capability(0)
        archs = torch.cuda.get_arch_list()
    except Exception:
        return True
    for arch in archs:
        kind, _, num = arch.partition("_")
        if not num.isdigit():
            continue
        a_major, a_minor = int(num) // 10, int(num) % 10
        if kind == "sm" and a_major == major and a_minor <= minor:
            return True
        if kind == "compute" and (a_major, a_minor) <= (major, minor):
            return True
    return False


def resolve(cfg):
    """把 auto / None 換成實際的值。"""
    cfg = dict(cfg)
    if cfg["device"] == "auto":
        cfg["device"] = "cuda" if torch.cuda.is_available() else "cpu"
    if cfg["device"].startswith("cuda") and not torch.cuda.is_available():
        print("=" * 70)
        print("警告：指定了 --device cuda，但 PyTorch 找不到 GPU，改用 CPU 和 CPU 設定。")
        print("Colab：執行階段 -> 變更執行階段類型 -> 選 T4 GPU，然後重新執行安裝那一格。")
        print("=" * 70, flush=True)
        cfg["device"] = "cpu"
    if cfg["device"].startswith("cuda") and not gpu_supported():
        major, minor = torch.cuda.get_device_capability(0)
        print("=" * 70)
        print("警告：%s（sm_%d%d）太新了，torch %s 只支援 %s，改用 CPU 和 CPU 設定。"
              % (torch.cuda.get_device_name(0), major, minor, torch.__version__,
                 " ".join(torch.cuda.get_arch_list())))
        print("這個專案的瓶頸是 CPU 上的遊戲模擬，用 CPU 訓練只會慢一點。")
        print("想用 GPU：Colab 的「變更執行階段類型」選 T4（L4、A100 都太新）。")
        print("=" * 70, flush=True)
        cfg["device"] = "cpu"
    profile = PROFILES["cuda" if cfg["device"].startswith("cuda") else "cpu"]
    if cfg.get("batch_size") is None:
        cfg["batch_size"] = profile["batch_size"]
    if cfg.get("n_steps") is None:
        # 每局收集的步數，取「n_steps x 局數剛好是 batch_size 的倍數」的最大值，每個 mini-batch 才會一樣大
        step = cfg["batch_size"] // math.gcd(cfg["batch_size"], cfg["n_envs"])
        step = step * max(1, -(-64 // step))            # 至少是 64 的倍數左右，太小的話 GAE 不準
        cfg["n_steps"] = max(step, profile["rollout"] // cfg["n_envs"] // step * step)
    out = Path(cfg["out_dir"])
    if cfg["resume"] == "auto":
        cfg["resume"] = str(out / "last_model.zip") if (out / "last_model.zip").exists() else ""
        if cfg["resume"] and not compatible(cfg["resume"]):
            cfg["resume"] = ""
            set_aside(out, model_obs_dim(out / "last_model.zip"))
    elif cfg["resume"] and not compatible(cfg["resume"]):
        raise SystemExit("不能接著訓練 %s：它的觀測長度是 %d，現在的遊戲是 %d（遊戲規則或觀測改過了）。"
                         "請改用新的 --out-dir，或用 --resume auto 讓它自動把舊的存檔移開。"
                         % (cfg["resume"], model_obs_dim(cfg["resume"]), OBS_DIM))
    return cfg


def set_aside(out, old_dim):
    """--resume auto 遇到舊規則的存檔：整個資料夾改名留著（不刪），然後從頭開始新的訓練。"""
    base = out.with_name("%s_old_obs%d" % (out.name, old_dim))
    dest, k = base, 2
    while dest.exists():
        dest, k = base.with_name("%s_%d" % (base.name, k)), k + 1
    out.rename(dest)
    print("=" * 70)
    print("%s 裡是舊規則的模型（觀測長度 %d，現在是 %d），不能接著練。" % (out, old_dim, OBS_DIM))
    print("已經把它改名成 %s（沒有刪除），從第 0 回合重新訓練。" % dest)
    print("=" * 70, flush=True)


def layers(text):
    return [int(x) for x in str(text).split(",") if x.strip()]


def schedule(cfg, step):
    """依目前步數算出 (學習率, clip_range, ent_coef)。學習率用等比的方式降，另外兩個用線性。"""
    span = max(1, cfg["anneal_end"] - cfg["anneal_start"])
    f = min(1.0, max(0.0, (step - cfg["anneal_start"]) / float(span)))
    lr = cfg["lr"] * (cfg["lr_end"] / cfg["lr"]) ** f
    clip = cfg["clip_range"] + (cfg["clip_end"] - cfg["clip_range"]) * f
    ent = cfg["ent_coef"] + (cfg["ent_end"] - cfg["ent_coef"]) * f
    return lr, clip, ent


def apply_hyperparams(model, cfg):
    """把 cfg 的超參數寫進模型。續訓時 PPO.load 會用存檔裡的舊值，所以載入後要再設一次。"""
    model.n_epochs = cfg["n_epochs"]
    model.batch_size = cfg["batch_size"]
    model.gamma = model.rollout_buffer.gamma = cfg["gamma"]
    model.gae_lambda = model.rollout_buffer.gae_lambda = cfg["gae_lambda"]
    model.vf_coef = cfg["vf_coef"]
    model.max_grad_norm = cfg["max_grad_norm"]
    model.target_kl = cfg["target_kl"] or None
    set_schedule(model, cfg)


def set_schedule(model, cfg):
    lr, clip, ent = schedule(cfg, model.num_timesteps)
    model.learning_rate = lr
    model.lr_schedule = lambda _: lr
    model.clip_range = lambda _: clip
    model.ent_coef = ent
    return lr, clip, ent


def score_key(stats):
    """選 best_model 的標準：先比通關數，再比平均關卡，最後比存活時間。"""
    return [stats["clears"], round(stats["stage"], 3), round(stats["survival"], 1)]


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
    def __init__(self, cfg, start_episodes=0, best=None):
        super(ProgressCallback, self).__init__()
        self.cfg = cfg
        self.out = Path(cfg["out_dir"])
        self.episodes = start_episodes
        self.best = best if isinstance(best, list) else None    # 舊版存的是一個數字，不能比
        self.recent = deque(maxlen=50)
        self.clears500 = deque(maxlen=500)
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
                self.clears500.append(1 if info.get("cleared", False) else 0)
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
        # 這裡在每次更新（model.train）之前呼叫。SB3 的 logger 這時還留著「上一次更新」的數值。
        train_vals = {k[6:]: v for k, v in self.model.logger.name_to_value.items() if k.startswith("train/")}
        lr, clip, ent = set_schedule(self.model, self.cfg)
        if not self.recent:
            return
        r = np.array([x[0] for x in self.recent])
        length = np.array([x[1] for x in self.recent])
        stage = np.array([x[2] for x in self.recent])
        clears = sum(1 for x in self.recent if x[3])
        elapsed = time.time() - self.start_time
        fps = (self.num_timesteps - self.start_steps) / max(elapsed, 1e-9)
        clear500 = sum(self.clears500) / float(len(self.clears500))
        print("step %10d  ep %5d | return %7.2f  length %6.0f  stage %.2f  clear %2d/%d  "
              "clear500 %4.1f%% | kl %.4f  lr %.1e | %5.0f steps/s | %6.0fs"
              % (self.num_timesteps, self.episodes, r.mean(), length.mean(), stage.mean(),
                 clears, len(self.recent), 100 * clear500, train_vals.get("approx_kl", float("nan")),
                 lr, fps, elapsed), flush=True)
        self._write_stats(train_vals, lr, clip, ent, r.mean(), clears / float(len(self.recent)), clear500)

    STATS_FIELDS = ["step", "episode", "lr", "clip_range", "ent_coef", "approx_kl", "clip_fraction",
                    "entropy_loss", "policy_gradient_loss", "value_loss", "explained_variance",
                    "return50", "clear50", "clear500"]

    def _write_stats(self, vals, lr, clip, ent, ret, clear50, clear500):
        path = self.out / "train_stats.csv"
        new = not path.exists()
        row = {"step": int(self.num_timesteps), "episode": self.episodes, "lr": lr, "clip_range": clip,
               "ent_coef": ent, "return50": ret, "clear50": clear50, "clear500": clear500}
        for key in self.STATS_FIELDS:
            if key not in row:
                v = vals.get(key, "")
                row[key] = "" if v == "" or (isinstance(v, float) and math.isnan(v)) else float(v)
        with open(str(path), "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=self.STATS_FIELDS)
            if new:
                w.writeheader()
            w.writerow(row)

    def _record(self, stats, model_file):
        return {"episode": self.episodes, "step": int(self.num_timesteps),
                "minutes": round((time.time() - self.start_time) / 60, 1),
                "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "eval": stats, "model": model_file}

    def _export_web(self):
        """把里程碑模型和最佳模型匯出成網頁版模型，網頁上的選單就能直接選。"""
        try:
            export_run(self.out, [self.out / "web", WEB_DIR / "model"])
        except Exception as exc:                     # 匯出失敗不應該讓訓練停下來
            print("  （網頁版匯出失敗：%s）" % exc, flush=True)

    def _save_milestone(self, m):
        path = self.out / "checkpoints" / ("ppo_ep%d.zip" % m)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.model.save(str(path))
        stats = evaluate(model_actor(self.model), self.cfg["milestone_eval"])
        print("  [第 %d 回合] 存檔 %s | %s" % (m, path, format_eval(stats)), flush=True)
        log = self.out / "milestones.json"
        records = json.loads(log.read_text()) if log.exists() else []
        records = [r for r in records if r["episode"] != m]
        rec = self._record(stats, "checkpoints/" + path.name)
        rec["episode"] = m
        records.append(rec)
        log.write_text(json.dumps(sorted(records, key=lambda r: r["episode"]),
                                  ensure_ascii=False, indent=2))
        self._export_web()

    def _evaluate(self):
        stats = evaluate(model_actor(self.model), self.cfg["eval_episodes"], seed=SELECT_SEED)
        print("  eval：%s" % format_eval(stats), flush=True)
        key = score_key(stats)
        if self.best is None or key > self.best:
            self.best = key
            self.model.save(str(self.out / "best_model.zip"))
            (self.out / "best.json").write_text(json.dumps(
                self._record(stats, "best_model.zip"), ensure_ascii=False, indent=2))
            print("  新的最佳模型 -> %s" % (self.out / "best_model.zip"), flush=True)
            self._export_web()
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

    start_episodes, best = 0, None
    if cfg["resume"]:
        model = PPO.load(cfg["resume"], env=venv, device=cfg["device"])
        if model.n_steps != cfg["n_steps"]:
            print("注意：存檔的 n_steps 是 %d，續訓時沿用（--n-steps 只對新的訓練有效）" % model.n_steps)
            cfg["n_steps"] = model.n_steps
        progress = Path(cfg["resume"]).with_name("last_progress.json")
        if progress.exists():
            saved = json.loads(progress.read_text())
            start_episodes, best = saved.get("episodes", 0), saved.get("best")
        print("從 %s 接著訓練（第 %d 步、第 %d 回合）"
              % (cfg["resume"], model.num_timesteps, start_episodes))
    else:
        model = PPO(
            "MlpPolicy", venv,
            n_steps=cfg["n_steps"], batch_size=cfg["batch_size"], n_epochs=cfg["n_epochs"],
            learning_rate=cfg["lr"], gamma=cfg["gamma"], gae_lambda=cfg["gae_lambda"],
            clip_range=cfg["clip_range"], ent_coef=cfg["ent_coef"], vf_coef=cfg["vf_coef"],
            max_grad_norm=cfg["max_grad_norm"], target_kl=cfg["target_kl"] or None,
            policy_kwargs=dict(net_arch=[dict(pi=layers(cfg["pi_layers"]), vf=layers(cfg["vf_layers"]))]),
            seed=cfg["seed"], device=cfg["device"], verbose=0)
    apply_hyperparams(model, cfg)          # 續訓時用這次命令列的超參數，不是存檔裡的

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
