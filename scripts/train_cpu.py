"""用 CPU 訓練 DQN 自動駕駛（不需要任何畫面）。

    python scripts/train_cpu.py                        # 300 萬步 -> models/dqn.pt
    python scripts/train_cpu.py --total-steps 500000   # 快速試跑，agent 比較弱
    python scripts/train_cpu.py --workers 4            # 用 4 個程序跑遊戲
    python scripts/train_cpu.py --eval-only            # 評估 models/dqn.pt
    python scripts/train_cpu.py --help                 # 列出所有超參數

CPU 設定：同時 8 局、256 單元的 MLP、batch 128、每 4 步做一次梯度更新。
"""
import multiprocessing
import os

import _bootstrap  # noqa: F401
from shmup.agent.trainer import build_arg_parser, run_eval_only, train

CPU_PROFILE = {
    "device": "cpu",
    "num_envs": 8,
    "workers": 0,
    "hidden": 256,
    "buffer_size": 300000,
    "batch_size": 128,
    "train_every": 4,
    "grad_steps": 1,
    "threads": max(1, min(4, (os.cpu_count() or 2) // 2)),
}


def main():
    args = build_arg_parser(__doc__, CPU_PROFILE).parse_args()
    cfg = {k: v for k, v in vars(args).items() if k != "eval_only"}
    cfg["device"] = "cpu"
    if args.eval_only:
        run_eval_only(cfg)
    else:
        train(cfg)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
