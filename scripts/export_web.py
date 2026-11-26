"""把遊戲規則和訓練好的 PPO 模型匯出給網頁版 demo 使用。

    python scripts/export_web.py                                   # 規則 + models/ppo/best_model.zip
    python scripts/export_web.py --model models/ppo/checkpoints/ppo_ep2000.zip
    python scripts/export_web.py --rules-only                      # 改過 core/rules.py 之後執行

接著用瀏覽器打開 web/index.html 即可。
"""
import argparse

import _bootstrap  # noqa: F401
from shmup.agent.export import write_model, write_rules
from shmup.paths import MODELS_DIR


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=str(MODELS_DIR / "ppo" / "best_model.zip"))
    ap.add_argument("--rules-only", action="store_true")
    args = ap.parse_args()

    print("已輸出", write_rules())
    if args.rules_only:
        return
    from stable_baselines3 import PPO   # 只有這裡需要 SB3
    model = PPO.load(args.model, device="cpu")
    meta = {"step": int(model.num_timesteps), "source": args.model.split("/")[-1]}
    print("已輸出", write_model(model.policy, meta))


if __name__ == "__main__":
    main()
