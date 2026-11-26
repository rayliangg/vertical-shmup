"""pygame 版和錄影用的推論：載入 SB3 的 PPO 模型，選機率最高的動作。"""
import numpy as np
import torch
from stable_baselines3 import PPO

from .features import OBS_DIM, observe


class PPOPolicy:
    def __init__(self, model):
        self.model = model
        self.last_obs = [0.0] * OBS_DIM

    @classmethod
    def load(cls, path):
        return cls(PPO.load(str(path), device="cpu"))

    def action_probs(self, world):
        """回傳 18 個動作的機率（策略網路的輸出）。"""
        obs = np.asarray(observe(world, self.last_obs), dtype=np.float32)
        with torch.no_grad():
            obs_t = torch.as_tensor(obs).unsqueeze(0)
            dist = self.model.policy.get_distribution(obs_t)
            return dist.distribution.probs[0].numpy()

    def __call__(self, world):
        """回傳目前局面機率最高的動作編號（不隨機，demo 用）。"""
        return int(self.action_probs(world).argmax())
