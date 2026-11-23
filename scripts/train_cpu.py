"""Train the DQN autopilot on the CPU.

    python scripts/train_cpu.py                        # 3M decisions -> models/dqn.pt
    python scripts/train_cpu.py --total-steps 500000   # quick, weaker agent
    python scripts/train_cpu.py --workers 4            # step games in 4 processes
    python scripts/train_cpu.py --eval-only            # score models/dqn.pt
    python scripts/train_cpu.py --help                 # every hyper-parameter

CPU profile: 8 games, 256-unit MLP, batch 128, one gradient step every 4 decisions.
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
