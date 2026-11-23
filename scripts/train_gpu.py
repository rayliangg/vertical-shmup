"""用 NVIDIA GPU（CUDA）訓練 DQN 自動駕駛，例如 Google Colab 的 T4。

    python scripts/train_gpu.py                        # 800 萬步 -> models/dqn.pt
    python scripts/train_gpu.py --device cuda:1        # 指定第幾張 GPU
    python scripts/train_gpu.py --workers 12           # 用更多程序跑遊戲
    python scripts/train_gpu.py --eval-only            # 評估 models/dqn.pt

GPU 設定：64 局分散在多個程序裡同時跑（遊戲邏輯是吃 CPU 的 Python）、
512 單元的 MLP、batch 512、每 16 步做 2 次梯度更新、用 pinned memory 加速
CPU -> GPU 的資料複製。只用 PyTorch 1.0 時代就有的 CUDA 功能；
Mac 沒有 CUDA，請改用 train_cpu.py。
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
        raise SystemExit("找不到 CUDA（Colab 請選 T4 GPU 執行階段），或改用 scripts/train_cpu.py。")
    torch.backends.cudnn.benchmark = True
    print("GPU:", torch.cuda.get_device_name(torch.device(cfg["device"])))
    if args.eval_only:
        run_eval_only(cfg)
    else:
        train(cfg)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
