"""命令列：python -m shmup <指令>

    play      自己玩（--autopilot 看 PPO 玩）
    train     訓練 PPO（不需要畫面；有 GPU 就用 GPU）
    eval      評估一個模型
    report    學習曲線 + 第 100/500/2000/5000 回合模型的結果表
    export    匯出遊戲規則和模型給網頁版

每個指令都可以加 --help 看所有參數。
"""
import argparse
import multiprocessing
from pathlib import Path

from .paths import MODELS_DIR

RUN_DIR = MODELS_DIR / "ppo"


def _add_train_args(p):
    from .rl.train import DEFAULTS
    for key, value in DEFAULTS.items():
        kind = {"n_steps": int, "batch_size": int}.get(key, type(value))
        p.add_argument("--" + key.replace("_", "-"), type=kind, default=value)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m shmup", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command")

    p = sub.add_parser("play", help="自己玩，或用 --autopilot 看 PPO 玩")
    p.add_argument("--autopilot", action="store_true")
    p.add_argument("--model", type=Path, default=RUN_DIR / "best_model.zip")
    p.add_argument("--seed", type=int, default=None, help="每一局都用固定的 seed")
    p.add_argument("--speed", type=int, default=1, help="每個畫面 frame 跑幾步模擬（加速用）")

    p = sub.add_parser("train", help="訓練 PPO（預設：用滿 CPU 核心、玩到 5000 回合）")
    _add_train_args(p)

    p = sub.add_parser("eval", help="用固定的 10 局評估一個模型")
    p.add_argument("model", nargs="?", default=str(RUN_DIR / "best_model.zip"))
    p.add_argument("--episodes", type=int, default=10)

    p = sub.add_parser("report", help="學習曲線 + 里程碑模型結果表")
    p.add_argument("--run-dir", default=str(RUN_DIR))
    p.add_argument("--episodes", type=int, default=100)

    p = sub.add_parser("export", help="匯出遊戲規則和所有里程碑模型給網頁版（訓練時會自動做）")
    p.add_argument("--run-dir", default=str(RUN_DIR))
    p.add_argument("--rules-only", action="store_true", help="只匯出規則（改過 game/rules.py 之後）")

    args = ap.parse_args(argv)
    cmd = args.command or "play"

    if cmd == "play":
        from .ui.app import App          # 真的要開視窗時才 import pygame（訓練不會用到）
        App(getattr(args, "autopilot", False), getattr(args, "model", None),
            getattr(args, "seed", None), getattr(args, "speed", 1)).run()
    elif cmd == "train":
        from .rl.train import train
        train({k: v for k, v in vars(args).items() if k != "command"})
    elif cmd == "eval":
        from stable_baselines3 import PPO
        from .rl.evaluate import evaluate, format_eval, model_actor
        model = PPO.load(args.model, device="cpu")
        print(format_eval(evaluate(model_actor(model), args.episodes)))
    elif cmd == "report":
        from .rl.evaluate import make_report
        make_report(args.run_dir, args.episodes)
    elif cmd == "export":
        from .paths import WEB_DIR
        from .rl.policy import export_run, write_rules
        print("已輸出", write_rules())
        if not args.rules_only:
            entries = export_run(args.run_dir, [WEB_DIR / "model"])
            print("已匯出 %d 個模型到 %s：%s" % (len(entries), WEB_DIR / "model",
                                           "、".join(e["label"] for e in entries)))


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
