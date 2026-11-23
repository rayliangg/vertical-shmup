"""Train the DQN autopilot on an NVIDIA GPU (CUDA).

    python scripts/train_gpu.py                        # 8M decisions -> models/dqn.pt
    python scripts/train_gpu.py --device cuda:1        # pick a GPU
    python scripts/train_gpu.py --workers 12           # more game processes
    python scripts/train_gpu.py --eval-only            # score models/dqn.pt

GPU profile: 64 games stepped in parallel worker processes (game logic is
CPU-bound Python), a 512-unit MLP, batch 512, 2 gradient steps every 16
decisions, pinned-memory host->GPU copies. Uses only PyTorch 1.0-era CUDA
features; Apple-silicon Macs have no CUDA, so use train_cpu.py there.
"""
import multiprocessing
import os

import torch

import _bootstrap  # noqa: F401
from shmup.agent.trainer import build_arg_parser, run_eval_only, train

GPU_PROFILE = {
    "device": "cuda",
    "total_steps": 8000000,
    "num_envs": 64,
    "workers": max(2, min((os.cpu_count() or 4) - 1, 12)),
    "hidden": 512,
    "buffer_size": 1000000,
    "batch_size": 512,
    "lr": 3e-4,
    "train_every": 16,
    "grad_steps": 2,
    "learning_starts": 50000,
    "eps_decay_steps": 2500000,
    "eval_every": 400000,
    "log_every": 100000,
}


def main():
    args = build_arg_parser(__doc__, GPU_PROFILE).parse_args()
    cfg = {k: v for k, v in vars(args).items() if k != "eval_only"}
    if not torch.cuda.is_available():
        raise SystemExit("CUDA is not available. Use scripts/train_cpu.py instead.")
    torch.backends.cudnn.benchmark = True
    print("GPU:", torch.cuda.get_device_name(torch.device(cfg["device"])))
    if args.eval_only:
        run_eval_only(cfg)
    else:
        train(cfg)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
