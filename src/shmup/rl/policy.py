"""訓練好的 PPO 模型怎麼「用」：載入、選動作、匯出給網頁版。

    PPOPolicy                   pygame 自動駕駛、錄影用：選機率最高的動作
    write_rules()               web/js/rules.js   （來自 shmup.game.rules，網頁版的遊戲規則）
    write_model(policy)         web/model/ppo_model.js（PPO 策略網路的權重，base64 float32）

匯出的都是一般的 script（不是 JSON），所以直接用 file:// 開 web/index.html 也能載入。
"""
import base64
import json

import numpy as np

from ..game import rules
from ..paths import WEB_DIR
from .features import ACTIONS, OBS_DIM, observe

HEADER = "// 由 python -m shmup export 自動產生，請不要手動修改。\n"
ACTIVATIONS = {"Tanh": "tanh", "ReLU": "relu"}


class PPOPolicy:
    def __init__(self, model):
        self.model = model
        self.last_obs = [0.0] * OBS_DIM

    @classmethod
    def load(cls, path):
        from stable_baselines3 import PPO
        return cls(PPO.load(str(path), device="cpu"))

    def action_probs(self, world):
        """回傳 18 個動作的機率（策略網路的輸出）。"""
        import torch
        obs = np.asarray(observe(world, self.last_obs), dtype=np.float32)
        with torch.no_grad():
            dist = self.model.policy.get_distribution(torch.as_tensor(obs).unsqueeze(0))
            return dist.distribution.probs[0].numpy()

    def __call__(self, world):
        """回傳目前局面機率最高的動作編號（不隨機，demo 用）。"""
        return int(self.action_probs(world).argmax())


# ---------------------------------------------------------------------------
# 匯出給網頁版
# ---------------------------------------------------------------------------
def rules_js():
    data = {k: getattr(rules, k) for k in dir(rules) if k.isupper()}
    body = json.dumps(data, indent=2, sort_keys=True)
    return (HEADER + "(function (S) {\n  S.RULES = " + body.replace("\n", "\n  ")
            + ";\n})(this.Shmup = this.Shmup || {});\n")


def write_rules(path=WEB_DIR / "js" / "rules.js"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rules_js())
    return path


def _b64(tensor):
    arr = tensor.detach().cpu().numpy().astype("<f4")
    return base64.b64encode(arr.tobytes()).decode("ascii")


def policy_layers(policy):
    """把 SB3 的策略網路（shared_net + policy_net + action_net）攤平成一串 Linear 層。

    每一層記下自己後面接的激活函數，網頁版照著算就能得到一樣的 logits。
    """
    import torch.nn as nn
    ext = policy.mlp_extractor
    modules = list(getattr(ext, "shared_net", [])) + list(ext.policy_net) + [policy.action_net]
    layers = []
    for module in modules:
        if isinstance(module, nn.Linear):
            layers.append({"in": module.in_features, "out": module.out_features,
                           "w": _b64(module.weight), "b": _b64(module.bias), "act": "none"})
        else:
            name = ACTIVATIONS.get(type(module).__name__)
            if name is None:
                raise ValueError("網頁版不支援這種激活函數：%s" % type(module).__name__)
            layers[-1]["act"] = name
    return layers


def write_model(policy, model_id, meta=None, path=None):
    """匯出一個模型給網頁版：註冊到 Shmup.MODELS_DATA[model_id]（網頁選單選到時才載入）。"""
    layers = policy_layers(policy)
    data = {"algo": "PPO", "obs_dim": layers[0]["in"], "n_actions": layers[-1]["out"],
            "hidden": layers[0]["out"], "actions": [list(a) for a in ACTIONS],
            "layers": layers, "meta": meta or {}}
    path = path or (WEB_DIR / "model" / ("ppo_%s.js" % model_id))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HEADER + "(function (S) { S.MODELS_DATA = S.MODELS_DATA || {}; "
                    "S.MODELS_DATA[%s] = %s; })(this.Shmup = this.Shmup || {});\n"
                    % (json.dumps(model_id), json.dumps(data, separators=(",", ":"))))
    return path


def write_manifest(entries, web_model_dir):
    """網頁選單的清單：有哪些模型、每個模型的評估結果。"""
    path = web_model_dir / "manifest.js"
    path.write_text(HEADER + "(function (S) { S.MODEL_LIST = "
                    + json.dumps(entries, ensure_ascii=False, indent=1)
                    + "; })(this.Shmup = this.Shmup || {});\n")
    return path


def export_run(run_dir, web_model_dirs):
    """把一次訓練的里程碑模型 + 最佳模型全部匯出給網頁版，並更新選單清單。

    訓練時每存一個里程碑就會自動呼叫；也可以用 python -m shmup export 手動執行。
    """
    from pathlib import Path
    from stable_baselines3 import PPO

    run_dir = Path(run_dir)
    records = {}
    if (run_dir / "milestones.json").exists():
        for r in json.loads((run_dir / "milestones.json").read_text()):
            records["ep%d" % r["episode"]] = r
    if (run_dir / "best.json").exists():
        records["best"] = json.loads((run_dir / "best.json").read_text())

    models = sorted((run_dir / "checkpoints").glob("ppo_ep*.zip"),
                    key=lambda p: int(p.stem.replace("ppo_ep", "")))
    if (run_dir / "best_model.zip").exists():
        models.append(run_dir / "best_model.zip")
    entries = []
    for zip_path in models:
        is_best = zip_path.name == "best_model.zip"
        model_id = "best" if is_best else zip_path.stem.replace("ppo_", "")
        rec = records.get(model_id, {})
        model = PPO.load(str(zip_path), device="cpu")
        meta = {"step": int(model.num_timesteps), "source": zip_path.name}
        label = ("最佳模型（第 %s 回合）" % rec.get("episode", "?")) if is_best \
            else "第 %s 回合" % model_id.replace("ep", "")
        entries.append({"id": model_id, "label": label, "file": "ppo_%s.js" % model_id,
                        "episode": rec.get("episode"), "step": meta["step"],
                        "eval": rec.get("eval")})
        for d in web_model_dirs:
            write_model(model.policy, model_id, meta, Path(d) / ("ppo_%s.js" % model_id))
    for d in web_model_dirs:
        write_manifest(entries, Path(d))
    return entries
