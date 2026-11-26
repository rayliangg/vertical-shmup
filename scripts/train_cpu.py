"""用 CPU 訓練 PPO 自動駕駛（Stable Baselines3，不需要任何畫面）。

    python scripts/train_cpu.py                           # 用全部核心玩到 2000 回合
    python scripts/train_cpu.py --max-episodes 300        # 快速試跑
    python scripts/train_cpu.py --resume models/ppo/last_model.zip     # 接著上次訓練
    python scripts/train_cpu.py --eval-only models/ppo/best_model.zip  # 只評估
    python scripts/train_cpu.py --help                    # 列出所有超參數

CPU 設定：同時玩「CPU 核心數」局（每局一個程序，用滿所有核心），
策略網路和價值網路各 2 層 x 256 單元；在第 10 / 50 / 500 / 2000 回合各存一份模型。
SB3 官方也建議 PPO + MLP 用 CPU 跑，通常比 GPU 快。
"""
import multiprocessing

import _bootstrap  # noqa: F401
from shmup.agent.train import build_arg_parser, run

CPU_PROFILE = {"device": "cpu"}


def main():
    args = build_arg_parser(__doc__, CPU_PROFILE).parse_args()
    cfg = {k: v for k, v in vars(args).items() if k != "eval_only"}
    run(cfg, args.eval_only)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
