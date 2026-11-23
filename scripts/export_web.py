"""把遊戲規則和訓練好的模型匯出給網頁版 demo 使用。

    python scripts/export_web.py                       # 規則 + models/dqn.pt
    python scripts/export_web.py --model models/dqn_last.pt
    python scripts/export_web.py --rules-only          # 改過 core/rules.py 之後執行

接著用瀏覽器打開 web/index.html 即可（不一定要開伺服器）。
"""
import argparse

import _bootstrap  # noqa: F401
from shmup.agent.export import write_model, write_rules
from shmup.paths import MODELS_DIR


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=str(MODELS_DIR / "dqn.pt"))
    ap.add_argument("--rules-only", action="store_true")
    args = ap.parse_args()

    print("已輸出", write_rules())
    if args.rules_only:
        return
    from shmup.agent.trainer import load_network   # 只有這裡需要 torch
    net, ckpt = load_network(args.model)
    meta = {"step": ckpt.get("step"), "eval": ckpt.get("eval")}
    print("已輸出", write_model(net, meta))


if __name__ == "__main__":
    main()
