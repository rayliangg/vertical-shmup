"""把 World 包成 Gym 風格的環境，另外提供單程序 / 多程序的向量環境。

agent 每做一次決策 = 遊戲前進 FRAME_SKIP 個 frame（每秒 30 次決策）。
"""
import multiprocessing as mp

import numpy as np

from ..core import World
from .features import ACTIONS, N_ACTIONS, OBS_DIM, observe

FRAME_SKIP = 2

# 獎勵設計：活下來、不要被打、撿道具、分數只給一點點。
REWARD_ALIVE = 0.01
REWARD_HP_LOST = -1.0
REWARD_BOMB_SPENT = -0.5        # 自動炸彈救了一命，但用掉了資源
REWARD_SHIELD_LOST = -0.3
REWARD_PICKUP = 0.05
REWARD_PER_SCORE = 0.0002       # 100 分 -> +0.02
REWARD_DEATH = -1.0


class ShmupEnv:
    """reset() -> obs；step(action) -> obs, reward, terminated, truncated, info。"""

    observation_size = OBS_DIM
    action_count = N_ACTIONS

    def __init__(self, seed=0, max_steps=9000):
        self.world = World(seed)
        self.seed = seed
        self.episode = 0
        self.max_steps = max_steps
        self.t = 0
        self._buf = [0.0] * OBS_DIM

    def _obs(self):
        return np.asarray(observe(self.world, self._buf), dtype=np.float32)

    def reset(self, seed=None):
        if seed is None:
            seed = self.seed * 1000003 + self.episode
        self.episode += 1
        self.world.reset(seed)
        self.t = 0
        return self._obs()

    def step(self, action):
        w = self.world
        dx, dy, focus = ACTIONS[action]
        score0 = w.score
        reward = REWARD_ALIVE
        hp_lost = 0
        for _ in range(FRAME_SKIP):
            hp_lost += w.step(dx, dy, focus)
            for name, _, _, value in w.events:
                if name == "bomb" and value:
                    reward += REWARD_BOMB_SPENT
                elif name == "shield":
                    reward += REWARD_SHIELD_LOST
                elif name == "pickup":
                    reward += REWARD_PICKUP
            if w.done:
                break
        self.t += 1
        reward += REWARD_HP_LOST * hp_lost + REWARD_PER_SCORE * (w.score - score0)
        terminated = w.done
        if terminated:
            reward += REWARD_DEATH
        truncated = not terminated and self.t >= self.max_steps
        info = {"hp_lost": hp_lost, "score": w.score, "stage": w.stage, "t": self.t}
        return self._obs(), reward, terminated, truncated, info


# ---------------------------------------------------------------------------
# 向量環境。兩種都會自動 reset：回合結束後回傳的 obs 是下一局的第一個 obs，
# 真正的最後一個 obs 放在 info["final_obs"]。
# ---------------------------------------------------------------------------
def _step_autoreset(env, action):
    obs, r, term, trunc, info = env.step(action)
    if term or trunc:
        info["final_obs"] = obs
        obs = env.reset()
    return obs, r, term, trunc, info


def _stack(results):
    obs, rew, term, trunc, infos = zip(*results)
    return (np.stack(obs), np.asarray(rew, np.float32), np.asarray(term, bool),
            np.asarray(trunc, bool), list(infos))


class SyncVectorEnv:
    def __init__(self, n, seed=0, max_steps=9000):
        self.envs = [ShmupEnv(seed * 10007 + i, max_steps) for i in range(n)]
        self.n = n

    def reset(self):
        return np.stack([e.reset() for e in self.envs])

    def step(self, actions):
        return _stack([_step_autoreset(e, int(a)) for e, a in zip(self.envs, actions)])

    def close(self):
        pass


def _worker(conn, seeds, max_steps):
    envs = [ShmupEnv(s, max_steps) for s in seeds]
    try:
        while True:
            cmd, data = conn.recv()
            if cmd == "step":
                conn.send([_step_autoreset(e, int(a)) for e, a in zip(envs, data)])
            elif cmd == "reset":
                conn.send([e.reset() for e in envs])
            else:
                break
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        conn.close()


class SubprocVectorEnv:
    """把 n 個環境分散到 `workers` 個程序（遊戲邏輯是吃 CPU 的 Python）。"""

    def __init__(self, n, workers, seed=0, max_steps=9000):
        workers = max(1, min(workers, n))
        seeds = [seed * 10007 + i for i in range(n)]
        chunks = [seeds[i::workers] for i in range(workers)]
        ctx = mp.get_context("spawn")
        self.conns, self.procs, self.sizes = [], [], []
        for chunk in chunks:
            parent, child = ctx.Pipe()
            proc = ctx.Process(target=_worker, args=(child, chunk, max_steps), daemon=True)
            proc.start()
            child.close()
            self.conns.append(parent)
            self.procs.append(proc)
            self.sizes.append(len(chunk))
        self.n = n

    def reset(self):
        for c in self.conns:
            c.send(("reset", None))
        return np.stack([o for c in self.conns for o in c.recv()])

    def step(self, actions):
        i = 0
        for c, size in zip(self.conns, self.sizes):
            c.send(("step", actions[i:i + size]))
            i += size
        return _stack([r for c in self.conns for r in c.recv()])

    def close(self):
        for c in self.conns:
            try:
                c.send(("close", None))
            except (BrokenPipeError, OSError):
                pass
        for p in self.procs:
            p.join(timeout=2)


def make_vector_env(n, workers=0, seed=0, max_steps=9000):
    if workers > 1:
        return SubprocVectorEnv(n, workers, seed, max_steps)
    return SyncVectorEnv(n, seed, max_steps)
