"""評估與報告：固定 seed 的評估、兩個對照組（baseline）、學習曲線圖、里程碑結果表。

    python -m shmup eval models/ppo/best_model.zip       # 評估一個模型
    python -m shmup report                               # 產生 models/ppo/report/

報告內容：
    learning_curve.png   每回合的總獎勵、存活長度、打到第幾關（50 回合移動平均）
    results.md           第 100 / 500 / 2000 / 5000 回合的模型 vs. 亂動 / 不動 兩個對照組（含 95% 信賴區間）
"""
import csv
import json
from pathlib import Path

import numpy as np

from .env import MAX_STEPS, ShmupEnv
from .features import N_ACTIONS

EVAL_SEED = 100000             # 報告、里程碑固定用 seed 100000、100001 …，不同模型才能公平比較
SELECT_SEED = 200000           # 訓練中挑 best_model 用另一組 seed，報告的局才不會被「挑過」
SECONDS_PER_STEP = 1.0 / 30    # 一次決策 = 2 frame = 1/30 秒


def evaluate(act, episodes=10, seed=EVAL_SEED, max_steps=MAX_STEPS):
    """用固定 seed 玩幾局。`act(obs) -> 動作編號`。"""
    env = ShmupEnv(max_steps)
    lengths, scores, stages, clears = [], [], [], 0
    for i in range(episodes):
        obs = env.reset_to(seed + i)
        while True:
            obs, _, done, info = env.step(act(obs))
            if done:
                break
        lengths.append(info["t"])
        scores.append(info["score"])
        stages.append(info["stage"])
        clears += 1 if info["cleared"] else 0
    return {"survival": float(np.mean(lengths)),
            "seconds": float(np.mean(lengths)) * SECONDS_PER_STEP,
            "score": float(np.mean(scores)), "stage": float(np.mean(stages)),
            "clears": clears, "episodes": episodes}


def wilson(k, n, z=1.96):
    """k/n 的 95% 信賴區間（Wilson, 1927）。局數少的時候，通關率的誤差其實很大。"""
    if n == 0:
        return 0.0, 0.0
    p = k / float(n)
    mid = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, mid - half), min(1.0, mid + half)


def model_actor(model):
    """SB3 模型 -> 選機率最高的動作（不隨機）。"""
    return lambda obs: int(model.predict(obs, deterministic=True)[0])


def random_actor(seed=0):
    rng = np.random.RandomState(seed)
    return lambda obs: int(rng.randint(N_ACTIONS))


def still_actor():
    return lambda obs: 0               # 動作 0 = 不動


def format_eval(s):
    return ("存活 %.0f 步（%.1f 秒）  分數 %.0f  平均第 %.2f 關  ALL CLEAR %d/%d"
            % (s["survival"], s["seconds"], s["score"], s["stage"], s["clears"], s["episodes"]))


# ---------------------------------------------------------------------------
# 報告
# ---------------------------------------------------------------------------
def read_monitor(run_dir):
    """讀 VecMonitor 寫的 part1.monitor.csv、part2…（續訓一次多一個檔案），依序接起來。"""
    rows = []
    parts = sorted(Path(run_dir).glob("part*.monitor.csv"),
                   key=lambda p: int(p.name.split(".")[0].replace("part", "")))
    for path in parts:
        with open(str(path)) as f:
            f.readline()                              # 第一行是 # 開頭的說明
            rows.extend(csv.DictReader(f))
    return rows


def moving_average(x, n=50):
    x = np.asarray(x, dtype=float)
    if len(x) < n:
        return x
    c = np.cumsum(np.insert(x, 0, 0.0))
    head = [x[:i + 1].mean() for i in range(n - 1)]
    return np.concatenate([head, (c[n:] - c[:-n]) / n])


def plot_learning_curve(run_dir, out_png):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = read_monitor(run_dir)
    if not rows:
        return None
    ep = np.arange(1, len(rows) + 1)
    ret = [float(r["r"]) for r in rows]
    length = [float(r["l"]) * SECONDS_PER_STEP for r in rows]
    stage = [float(r.get("stage") or 1) for r in rows]
    fig, axes = plt.subplots(3, 1, figsize=(8, 9), sharex=True)
    for ax, y, title in ((axes[0], ret, "Episode return"),
                         (axes[1], length, "Survival time (s)"),
                         (axes[2], stage, "Stage reached")):
        ax.plot(ep, y, color="#9bb7d4", linewidth=0.6, label="each episode")
        ax.plot(ep, moving_average(y), color="#d4502a", linewidth=2, label="50-episode average")
        ax.set_ylabel(title)
        ax.grid(alpha=0.3)
    axes[0].legend(loc="upper left")
    axes[2].set_xlabel("Episode")
    fig.suptitle("PPO training (%d episodes)" % len(rows))
    fig.tight_layout()
    fig.savefig(str(out_png), dpi=120)
    plt.close(fig)
    return out_png


def make_report(run_dir, episodes=100):
    """畫學習曲線，並用同樣的局數評估每個里程碑模型和兩個對照組。"""
    from stable_baselines3 import PPO

    run_dir = Path(run_dir)
    out = run_dir / "report"
    out.mkdir(parents=True, exist_ok=True)
    png = plot_learning_curve(run_dir, out / "learning_curve.png")

    rows = [("不動（對照組）", evaluate(still_actor(), episodes)),
            ("亂動（對照組）", evaluate(random_actor(), episodes))]
    ckpts = sorted((run_dir / "checkpoints").glob("ppo_ep*.zip"),
                   key=lambda p: int(p.stem.replace("ppo_ep", "")))
    for path in ckpts + ([run_dir / "best_model.zip"] if (run_dir / "best_model.zip").exists() else []):
        model = PPO.load(str(path), device="cpu")
        name = ("第 %s 回合" % path.stem.replace("ppo_ep", "")) if path.stem.startswith("ppo_ep") \
            else "best_model"
        rows.append((name, evaluate(model_actor(model), episodes)))
        print("  %-14s %s" % (name, format_eval(rows[-1][1])))

    lines = ["# 訓練結果", "",
             "每個模型都用同樣的 %d 局（seed %d～%d）、選機率最高的動作來評估。"
             % (episodes, EVAL_SEED, EVAL_SEED + episodes - 1), "",
             "| 模型 | 平均存活 | 平均分數 | 平均第幾關 | ALL CLEAR | 通關率 95% 信賴區間 |",
             "|------|---------:|---------:|-----------:|----------:|--------------------:|"]
    for name, s in rows:
        lo, hi = wilson(s["clears"], s["episodes"])
        s["clear_ci"] = [lo, hi]
        lines.append("| %s | %.1f 秒 | %.0f | %.2f | %d / %d | %.0f%%～%.0f%% |"
                     % (name, s["seconds"], s["score"], s["stage"], s["clears"], s["episodes"],
                        100 * lo, 100 * hi))
    if png:
        lines += ["", "![學習曲線](learning_curve.png)"]
    (out / "results.md").write_text("\n".join(lines) + "\n")
    (out / "results.json").write_text(json.dumps({n: s for n, s in rows}, ensure_ascii=False, indent=2))
    print("報告：%s" % (out / "results.md"))
    return out
