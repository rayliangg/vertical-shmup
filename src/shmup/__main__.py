"""命令列進入點。

    python -m shmup                    # 自己玩
    python -m shmup --autopilot        # 看訓練好的 PPO 玩
    python -m shmup --autopilot --speed 3
"""
import argparse
from pathlib import Path


def main(argv=None):
    ap = argparse.ArgumentParser(prog="shmup", description="縱向彈幕射擊遊戲")
    ap.add_argument("--autopilot", action="store_true", help="讓 PPO agent 自動駕駛")
    ap.add_argument("--model", type=Path, default=None, help="模型檔（預設 models/ppo/best_model.zip）")
    ap.add_argument("--seed", type=int, default=None, help="每一局都用固定的 seed")
    ap.add_argument("--speed", type=int, default=1, help="每個畫面 frame 跑幾步模擬（加速用）")
    args = ap.parse_args(argv)

    from .client.app import App          # 真的要開視窗時才 import pygame（訓練不會用到）
    App(args.autopilot, args.model, args.seed, args.speed).run()


if __name__ == "__main__":
    main()
