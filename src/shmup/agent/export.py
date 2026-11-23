"""把遊戲規則和訓練好的網路匯出給網頁版。

    web/js/rules.js          Shmup.RULES（來自 shmup.core.rules）
    web/model/dqn_model.js   Shmup.MODEL（權重用 base64 存 float32，little-endian）

兩個都是一般的 script（不是 JSON），所以直接用 file:// 開 web/index.html 也能載入。
"""
import base64
import json

import numpy as np

from ..core import rules
from ..paths import WEB_DIR
from .features import ACTIONS

HEADER = "// 由 scripts/export_web.py 自動產生，請不要手動修改。\n"


def rules_dict():
    return {k: getattr(rules, k) for k in dir(rules) if k.isupper()}


def rules_js():
    body = json.dumps(rules_dict(), indent=2, sort_keys=True)
    return (HEADER + "(function (S) {\n  S.RULES = " + body.replace("\n", "\n  ")
            + ";\n})(this.Shmup = this.Shmup || {});\n")


def write_rules(path=WEB_DIR / "js" / "rules.js"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rules_js())
    return path


def _b64(tensor):
    arr = tensor.detach().cpu().numpy().astype("<f4")
    return base64.b64encode(arr.tobytes()).decode("ascii")


def model_dict(net, meta=None):
    layers = {}
    for name, linears in net.layers().items():
        layers[name] = [{"in": l.in_features, "out": l.out_features,
                         "w": _b64(l.weight), "b": _b64(l.bias)} for l in linears]
    return {"obs_dim": net.obs_dim, "n_actions": net.n_actions, "hidden": net.hidden,
            "actions": [list(a) for a in ACTIONS], "layers": layers, "meta": meta or {}}


def write_model(net, meta=None, path=WEB_DIR / "model" / "dqn_model.js"):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(model_dict(net, _jsonable(meta)), separators=(",", ":"))
    path.write_text(HEADER + "(function (S) { S.MODEL = " + data
                    + "; })(this.Shmup = this.Shmup || {});\n")
    return path


def _jsonable(obj):
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (np.generic,)):
        return obj.item()
    return obj
