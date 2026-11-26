"""把遊戲規則和訓練好的網路匯出給網頁版。

    web/js/rules.js          Shmup.RULES（來自 shmup.core.rules）
    web/model/ppo_model.js   Shmup.MODEL（PPO 策略網路的權重，base64 存 float32，little-endian）

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


ACTIVATIONS = {"Tanh": "tanh", "ReLU": "relu"}


def policy_layers(policy):
    """把 SB3 的策略網路（mlp_extractor.policy_net + action_net）攤平成一串 Linear 層。

    每一層記下自己後面接的激活函數，網頁版照著算就能得到一樣的 logits。
    """
    import torch.nn as nn
    layers = []
    for module in list(policy.mlp_extractor.policy_net) + [policy.action_net]:
        if isinstance(module, nn.Linear):
            layers.append({"in": module.in_features, "out": module.out_features,
                           "w": _b64(module.weight), "b": _b64(module.bias), "act": "none"})
        else:
            name = ACTIVATIONS.get(type(module).__name__)
            if name is None:
                raise ValueError("網頁版不支援這種激活函數：%s" % type(module).__name__)
            layers[-1]["act"] = name
    return layers


def model_dict(policy, meta=None):
    layers = policy_layers(policy)
    return {"algo": "PPO", "obs_dim": layers[0]["in"], "n_actions": layers[-1]["out"],
            "hidden": layers[0]["out"], "actions": [list(a) for a in ACTIONS],
            "layers": layers, "meta": meta or {}}


def write_model(policy, meta=None, path=WEB_DIR / "model" / "ppo_model.js"):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(model_dict(policy, _jsonable(meta)), separators=(",", ":"))
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
