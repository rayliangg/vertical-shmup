"""The browser port must simulate exactly like the Python game the agent trains on."""
import json
import math
import shutil
import subprocess

import pytest

from shmup.agent.export import rules_js
from shmup.agent.features import ACTIONS, observe
from shmup.core import World
from shmup.paths import ROOT, WEB_DIR

NODE = shutil.which("node")
HARNESS = ROOT / "tests" / "js_harness.js"
FRAMES = 15000                 # long enough to beat the first boss


def python_trace(seed, frames, net=None):
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
            if net is not None:
                import torch
                with torch.no_grad():
                    row["q"] = net(torch.tensor([obs], dtype=torch.float32))[0].tolist()
            trace.append(row)
    return trace


def node_trace(seed, frames, model_js=None):
    cmd = [NODE, str(HARNESS), str(WEB_DIR), str(seed), str(frames)]
    if model_js:
        cmd.append(str(model_js))
    return json.loads(subprocess.check_output(cmd))


def test_rules_js_is_up_to_date():
    assert (WEB_DIR / "js" / "rules.js").read_text() == rules_js(), \
        "web/js/rules.js is stale: run python scripts/export_web.py --rules-only"


@pytest.mark.skipif(NODE is None, reason="node.js not installed")
@pytest.mark.parametrize("seed", [1, 42])
def test_simulation_matches_browser(seed):
    py, js = python_trace(seed, FRAMES), node_trace(seed, FRAMES)
    assert len(py) == len(js)
    assert py[-1]["stage"] >= 2, "trace should reach a boss fight and stage 2"
    for a, b in zip(py, js):
        for key in ("frame", "score", "stage", "bullets", "enemies", "items", "state"):
            assert a[key] == b[key], (key, a["frame"], a[key], b[key])
        assert math.isclose(a["x"], b["x"], abs_tol=1e-9)
        assert math.isclose(a["y"], b["y"], abs_tol=1e-9)
        for i, (u, v) in enumerate(zip(a["obs"], b["obs"])):
            assert math.isclose(u, v, abs_tol=1e-9), ("obs", a["frame"], i, u, v)


@pytest.mark.skipif(NODE is None, reason="node.js not installed")
def test_exported_network_matches_torch(tmp_path):
    torch = pytest.importorskip("torch")
    from shmup.agent.dqn import DuelingQNetwork
    from shmup.agent.export import write_model
    from shmup.agent.features import N_ACTIONS, OBS_DIM

    torch.manual_seed(0)
    net = DuelingQNetwork(OBS_DIM, N_ACTIONS, hidden=64).eval()
    model_js = write_model(net, {"step": 0}, tmp_path / "model.js")
    py, js = python_trace(3, 600, net), node_trace(3, 600, model_js)
    for a, b in zip(py, js):
        for u, v in zip(a["q"], b["q"]):
            assert math.isclose(u, v, rel_tol=1e-4, abs_tol=1e-5)
