"""網頁版的模擬必須和訓練用的 Python 版完全一樣。"""
import json
import math
import shutil
import subprocess

import pytest

from shmup.rl.policy import rules_js
from shmup.rl.features import ACTIONS, observe
from shmup.game import World
from shmup.paths import ROOT, WEB_DIR

NODE = shutil.which("node")
HARNESS = ROOT / "tests" / "js_harness.js"
FRAMES = 30000                 # 夠長，三種關卡魔王都會出現


def python_trace(seed, frames, policy=None):
    w, trace = World(seed), []
    for f in range(frames):
        a = ACTIONS[(f * 7 // 13) % len(ACTIONS)]
        w.step(a[0], a[1], a[2], f % 997 == 500)
        w.player.hp = 5
        if f % 25 == 0:
            obs = observe(w)
            row = {"frame": w.frame, "score": w.score, "stage": w.stage,
                   "bullets": len(w.bullets), "enemies": len(w.enemies), "items": len(w.items),
                   "x": w.player.x, "y": w.player.y, "state": w.rng.state, "obs": obs}
            if policy is not None:
                import torch
                with torch.no_grad():
                    dist = policy.get_distribution(torch.tensor([obs], dtype=torch.float32))
                    row["probs"] = dist.distribution.probs[0].tolist()
            trace.append(row)
    return trace


def node_trace(seed, frames, model_js=None):
    cmd = [NODE, str(HARNESS), str(WEB_DIR), str(seed), str(frames)]
    if model_js:
        cmd.append(str(model_js))
    return json.loads(subprocess.check_output(cmd))


def test_rules_js_is_up_to_date():
    assert (WEB_DIR / "js" / "rules.js").read_text() == rules_js(), \
        "web/js/rules.js 過期了：請執行 python -m shmup export --rules-only"


@pytest.mark.skipif(NODE is None, reason="沒有安裝 node.js")
@pytest.mark.parametrize("seed", [1, 42])
def test_simulation_matches_browser(seed):
    py, js = python_trace(seed, FRAMES), node_trace(seed, FRAMES)
    assert len(py) == len(js)
    assert py[-1]["stage"] >= 2, "模擬應該要打到魔王並進入第 2 關"
    for a, b in zip(py, js):
        for key in ("frame", "score", "stage", "bullets", "enemies", "items", "state"):
            assert a[key] == b[key], (key, a["frame"], a[key], b[key])
        assert math.isclose(a["x"], b["x"], abs_tol=1e-9)
        assert math.isclose(a["y"], b["y"], abs_tol=1e-9)
        for i, (u, v) in enumerate(zip(a["obs"], b["obs"])):
            assert math.isclose(u, v, abs_tol=1e-9), ("obs", a["frame"], i, u, v)


@pytest.mark.skipif(NODE is None, reason="沒有安裝 node.js")
def test_exported_policy_matches_torch(tmp_path):
    """匯出到網頁版的 PPO 策略網路，在 JS 算出的動作機率要和 PyTorch 一樣。"""
    pytest.importorskip("stable_baselines3")
    from stable_baselines3 import PPO
    from shmup.rl.env import ShmupEnv
    from shmup.rl.policy import write_model

    model = PPO("MlpPolicy", ShmupEnv(), seed=0, device="cpu",
                policy_kwargs=dict(net_arch=[dict(pi=[64, 64], vf=[64, 64])]))
    model_js = write_model(model.policy, "test", {"step": 0}, tmp_path / "model.js")
    py, js = python_trace(3, 600, model.policy), node_trace(3, 600, model_js)
    for a, b in zip(py, js):
        for u, v in zip(a["probs"], b["probs"]):
            assert math.isclose(u, v, rel_tol=1e-4, abs_tol=1e-6)
