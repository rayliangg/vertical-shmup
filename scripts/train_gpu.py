"""用 NVIDIA GPU（CUDA）訓練 PPO 自動駕駛，例如 Google Colab 的 T4。

    python scripts/train_gpu.py                           # 玩到 2000 回合
    python scripts/train_gpu.py --resume models/ppo/last_model.zip

GPU 設定：網路更大（512 單元）、每次更新的 batch 更大（1024）。
遊戲模擬還是在 CPU 上跑（每局一個程序），所以 GPU 主要是讓「更新網路」這一步變快；
這個網路很小，CPU 版通常也不會比較慢。Mac 沒有 CUDA，請用 train_cpu.py。
"""
import multiprocessing

import torch

import _bootstrap  # noqa: F401
from shmup.agent.train import build_arg_parser, run

GPU_PROFILE = {"device": "cuda", "hidden": 512, "batch_size": 1024, "n_steps": 2048}


def main():
    args = build_arg_parser(__doc__, GPU_PROFILE).parse_args()
    cfg = {k: v for k, v in vars(args).items() if k != "eval_only"}
    if cfg["device"].startswith("cuda") and not torch.cuda.is_available():
        raise SystemExit("找不到 CUDA（Colab 請選 T4 GPU 執行階段），或改用 scripts/train_cpu.py。")
    if cfg["device"].startswith("cuda"):
        print("GPU:", torch.cuda.get_device_name(0))
    run(cfg, args.eval_only)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
