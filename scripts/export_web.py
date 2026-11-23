"""Export the game rules and a trained model for the browser demo.

    python scripts/export_web.py                       # rules + models/dqn.pt
    python scripts/export_web.py --model models/dqn_last.pt
    python scripts/export_web.py --rules-only          # after editing core/rules.py

Then open web/index.html in a browser (no server needed).
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

    print("wrote", write_rules())
    if args.rules_only:
        return
    from shmup.agent.trainer import load_network   # torch only needed here
    net, ckpt = load_network(args.model)
    meta = {"step": ckpt.get("step"), "eval": ckpt.get("eval")}
    print("wrote", write_model(net, meta))


if __name__ == "__main__":
    main()
