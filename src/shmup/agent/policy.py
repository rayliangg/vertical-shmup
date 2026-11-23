"""Greedy policy used by the pygame client to fly the ship."""
import numpy as np
import torch

from .features import OBS_DIM, observe
from .trainer import load_network


class DQNPolicy:
    def __init__(self, net):
        self.net = net
        self.last_obs = [0.0] * OBS_DIM

    @classmethod
    def load(cls, path):
        net, _ = load_network(path, "cpu")
        return cls(net)

    def q_values(self, world):
        x = torch.from_numpy(np.asarray(observe(world, self.last_obs), dtype=np.float32))
        with torch.no_grad():
            return self.net(x.unsqueeze(0))[0].numpy()

    def __call__(self, world):
        """Return the greedy action index for the current world state."""
        return int(self.q_values(world).argmax())
