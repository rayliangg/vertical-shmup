"""把 World 包成 gymnasium 環境，給 Stable Baselines3 用。

agent 每做一次決策 = 遊戲前進 FRAME_SKIP 個 frame（每秒 30 次決策）。
觀測是 features.py 的 284 個數字，動作是 18 種（9 個方向 x 一般 / 慢速）。
"""
import gymnasium as gym
import numpy as np

from ..core import World
from .features import ACTIONS, N_ACTIONS, OBS_DIM, observe

FRAME_SKIP = 2
MAX_STEPS = 15000               # 一局最多 15000 次決策（約 8 分鐘，夠打完 2 關）

# 獎勵設計：活下來、不要被打、撿道具、分數只給一點點。
REWARD_ALIVE = 0.01
REWARD_HP_LOST = -1.0
REWARD_BOMB_SPENT = -0.5        # 自動炸彈救了一命，但用掉了資源
REWARD_SHIELD_LOST = -0.3
REWARD_PICKUP = 0.05
REWARD_PER_SCORE = 0.0002       # 100 分 -> +0.02
REWARD_DEATH = -1.0
REWARD_CLEAR = 5.0              # 打倒最後一關的兩隻魔王（ALL CLEAR）


class ShmupEnv(gym.Env):
    """reset() -> (obs, info)；step(action) -> (obs, reward, terminated, truncated, info)。"""

    metadata = {"render_modes": []}

    def __init__(self, max_steps=MAX_STEPS):
        super(ShmupEnv, self).__init__()
        self.observation_space = gym.spaces.Box(-np.inf, np.inf, shape=(OBS_DIM,), dtype=np.float32)
        self.action_space = gym.spaces.Discrete(N_ACTIONS)
        self.max_steps = max_steps
        self.world = World(0)
        self.t = 0
        self._buf = [0.0] * OBS_DIM

    def _obs(self):
        return np.asarray(observe(self.world, self._buf), dtype=np.float32)

    def reset(self, *, seed=None, options=None):
        super(ShmupEnv, self).reset(seed=seed)
        # 遊戲本身的 seed：有指定就用指定的（評估用），沒有就從 gymnasium 的亂數抽一個
        game_seed = seed if seed is not None else int(self.np_random.integers(0, 2 ** 31 - 1))
        self.world.reset(game_seed)
        self.t = 0
        return self._obs(), {}

    def step(self, action):
        w = self.world
        dx, dy, focus = ACTIONS[int(action)]
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
            if w.player.hp <= 0:
                reward += REWARD_DEATH
            elif w.cleared:
                reward += REWARD_CLEAR
        truncated = not terminated and self.t >= self.max_steps
        info = {"hp_lost": hp_lost, "score": w.score, "stage": w.stage, "t": self.t,
                "cleared": w.cleared}
        return self._obs(), float(reward), terminated, truncated, info
