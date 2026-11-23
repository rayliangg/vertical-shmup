"""Training loop, evaluation and checkpoints for the DQN autopilot.

Entry points: scripts/train_cpu.py and scripts/train_gpu.py.
"""
import argparse
import json
import time
from collections import OrderedDict
from pathlib import Path

import numpy as np
import torch

from ..paths import MODELS_DIR
from .dqn import DuelingQNetwork, NStepWriter, ReplayBuffer, double_dqn_loss
from .env import ShmupEnv, make_vector_env
from .features import N_ACTIONS, OBS_DIM

DEFAULTS = OrderedDict([
    ("device", "cpu"),
    ("total_steps", 3000000),      # agent decisions summed over all envs
    ("num_envs", 8),
    ("workers", 0),                # >1: step envs in that many processes
    ("max_episode_steps", 9000),   # 5 minutes of play
    ("hidden", 256),
    ("buffer_size", 300000),
    ("batch_size", 128),
    ("lr", 2.5e-4),
    ("gamma", 0.99),
    ("n_step", 3),
    ("learning_starts", 20000),
    ("train_every", 4),            # env decisions per training round
    ("grad_steps", 1),             # gradient steps per training round
    ("target_update", 2000),       # gradient steps between target-network syncs
    ("eps_start", 1.0),
    ("eps_end", 0.02),
    ("eps_decay_steps", 1000000),
    ("max_grad_norm", 10.0),
    ("eval_every", 150000),
    ("eval_episodes", 10),
    ("log_every", 25000),
    ("seed", 1),
    ("threads", 0),                # torch CPU threads, 0 = library default
    ("save_path", str(MODELS_DIR / "dqn.pt")),
])


def build_arg_parser(description, overrides):
    """CLI with every hyper-parameter as a flag; `overrides` sets the defaults."""
    cfg = OrderedDict(DEFAULTS)
    cfg.update(overrides)
    ap = argparse.ArgumentParser(description=description,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    for key, value in cfg.items():
        ap.add_argument("--" + key.replace("_", "-"), type=type(value), default=value)
    ap.add_argument("--eval-only", action="store_true",
                    help="evaluate the checkpoint at --save-path instead of training")
    return ap


def epsilon_at(cfg, step):
    frac = min(float(step) / cfg["eps_decay_steps"], 1.0)
    return cfg["eps_start"] + (cfg["eps_end"] - cfg["eps_start"]) * frac


# ---------------------------------------------------------------------------
# Checkpoints
# ---------------------------------------------------------------------------
def save_checkpoint(net, cfg, path, extra=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    state = OrderedDict((k, v.detach().cpu()) for k, v in net.state_dict().items())
    payload = {"model": state, "obs_dim": net.obs_dim, "n_actions": net.n_actions,
               "hidden": net.hidden, "config": dict(cfg)}
    payload.update(extra or {})
    torch.save(payload, str(path))


def load_network(path, device="cpu"):
    ckpt = torch.load(str(path), map_location=device)
    net = DuelingQNetwork(ckpt["obs_dim"], ckpt["n_actions"], ckpt["hidden"])
    net.load_state_dict(ckpt["model"])
    return net.to(device).eval(), ckpt


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
def evaluate(net, device, episodes=10, max_steps=9000, seed=100000):
    """Greedy play on fixed seeds."""
    was_training = net.training
    net.eval()
    env = ShmupEnv(seed=0, max_steps=max_steps)
    lengths, scores, stages, hp_lost = [], [], [], 0
    with torch.no_grad():
        for ep in range(episodes):
            obs = env.reset(seed + ep)
            while True:
                q = net(torch.from_numpy(obs).to(device).unsqueeze(0))
                obs, _, term, trunc, info = env.step(int(q.argmax(1).item()))
                hp_lost += info["hp_lost"]
                if term or trunc:
                    break
            lengths.append(info["t"])
            scores.append(info["score"])
            stages.append(info["stage"])
    net.train(was_training)
    minutes = sum(lengths) / 1800.0
    return {"survival": float(np.mean(lengths)),
            "full_runs": int(sum(t >= max_steps for t in lengths)),
            "hp_lost_per_min": hp_lost / max(minutes, 1e-9),
            "score": float(np.mean(scores)),
            "stage": float(np.mean(stages))}


def run_eval_only(cfg):
    net, ckpt = load_network(cfg["save_path"], cfg["device"])
    print("checkpoint step:", ckpt.get("step"))
    stats = evaluate(net, torch.device(cfg["device"]), 30, cfg["max_episode_steps"])
    print(json.dumps(stats, indent=2))


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------
def train(cfg):
    torch.manual_seed(cfg["seed"])
    np.random.seed(cfg["seed"])
    if cfg["threads"] > 0:
        torch.set_num_threads(cfg["threads"])
    device = torch.device(cfg["device"])
    pin = device.type == "cuda"

    online = DuelingQNetwork(OBS_DIM, N_ACTIONS, cfg["hidden"]).to(device)
    target = DuelingQNetwork(OBS_DIM, N_ACTIONS, cfg["hidden"]).to(device)
    target.load_state_dict(online.state_dict())
    target.eval()
    optimizer = torch.optim.Adam(online.parameters(), lr=cfg["lr"], eps=1.5e-4)

    buffer = ReplayBuffer(cfg["buffer_size"], OBS_DIM, cfg["seed"])
    writer = NStepWriter(cfg["num_envs"], cfg["n_step"], cfg["gamma"], buffer)
    envs = make_vector_env(cfg["num_envs"], cfg["workers"], cfg["seed"],
                           cfg["max_episode_steps"])
    rng = np.random.RandomState(cfg["seed"])
    n_params = sum(p.numel() for p in online.parameters())
    print("device=%s envs=%d workers=%d obs=%d actions=%d params=%d"
          % (device, cfg["num_envs"], cfg["workers"], OBS_DIM, N_ACTIONS, n_params))
    print(json.dumps(cfg))

    def to_device(array):
        t = torch.from_numpy(array)
        if pin:
            return t.pin_memory().to(device, non_blocking=True)
        return t.to(device)

    obs = envs.reset()
    step = grad_steps = 0
    returns = np.zeros(cfg["num_envs"])
    recent_returns, recent_lengths, losses = [], [], []
    best = -1.0
    start = last_log_time = time.time()
    next_log, next_eval = cfg["log_every"], cfg["eval_every"]
    save_path = Path(cfg["save_path"])
    last_path = save_path.with_name(save_path.stem + "_last" + save_path.suffix)

    try:
        while step < cfg["total_steps"]:
            # act: epsilon-greedy over the whole batch of envs
            eps = epsilon_at(cfg, step)
            with torch.no_grad():
                actions = online(to_device(obs)).argmax(1).cpu().numpy()
            explore = rng.rand(cfg["num_envs"]) < eps
            actions[explore] = rng.randint(0, N_ACTIONS, size=int(explore.sum()))

            next_obs, rewards, terms, truncs, infos = envs.step(actions)
            for i in range(cfg["num_envs"]):
                ended = terms[i] or truncs[i]
                real_next = infos[i]["final_obs"] if ended else next_obs[i]
                writer.add(i, obs[i], actions[i], rewards[i], real_next, terms[i], truncs[i])
                returns[i] += rewards[i]
                if ended:
                    recent_returns.append(returns[i])
                    recent_lengths.append(infos[i]["t"])
                    returns[i] = 0.0
            obs = next_obs
            prev_step, step = step, step + cfg["num_envs"]

            # learn
            if len(buffer) >= cfg["learning_starts"]:
                rounds = step // cfg["train_every"] - prev_step // cfg["train_every"]
                for _ in range(rounds * cfg["grad_steps"]):
                    batch = [to_device(a) for a in buffer.sample(cfg["batch_size"])]
                    loss = double_dqn_loss(online, target, batch)
                    optimizer.zero_grad()
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(online.parameters(), cfg["max_grad_norm"])
                    optimizer.step()
                    grad_steps += 1
                    if grad_steps % 50 == 0:
                        losses.append(loss.item())
                    if grad_steps % cfg["target_update"] == 0:
                        target.load_state_dict(online.state_dict())

            # log, evaluate, save
            if step >= next_log:
                next_log += cfg["log_every"]
                now = time.time()
                speed = cfg["log_every"] / max(now - last_log_time, 1e-9)
                last_log_time = now
                print("step %10d  eps %.3f | return %8.2f  length %6.0f | loss %.4f | "
                      "%5.0f steps/s | %6.0fs"
                      % (step, eps, _mean(recent_returns[-50:]), _mean(recent_lengths[-50:]),
                         _mean(losses[-50:]), speed, now - start), flush=True)
            if step >= next_eval:
                next_eval += cfg["eval_every"]
                stats = evaluate(online, device, cfg["eval_episodes"], cfg["max_episode_steps"])
                print("  eval: survival %.0f  full %d/%d  hp_lost/min %.2f  score %.0f  stage %.2f"
                      % (stats["survival"], stats["full_runs"], cfg["eval_episodes"],
                         stats["hp_lost_per_min"], stats["score"], stats["stage"]), flush=True)
                save_checkpoint(online, cfg, last_path, {"step": step, "eval": stats})
                if stats["survival"] > best:
                    best = stats["survival"]
                    save_checkpoint(online, cfg, save_path, {"step": step, "eval": stats})
                    print("  new best -> %s" % save_path, flush=True)
    except KeyboardInterrupt:
        print("interrupted; saving %s" % last_path)
        save_checkpoint(online, cfg, last_path, {"step": step})
    finally:
        envs.close()
    if best < 0:
        save_checkpoint(online, cfg, save_path, {"step": step})
    print("done. Export for the browser with: python scripts/export_web.py")
    return online


def _mean(values):
    return float(np.mean(values)) if len(values) else float("nan")
