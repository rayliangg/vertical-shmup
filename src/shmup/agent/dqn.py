"""DQN building blocks, restricted to techniques published before 2019.

* Deep Q-Network, experience replay, target network ... Mnih et al., Nature 2015
* Double DQN target ................................. van Hasselt et al., AAAI 2016
* Dueling value/advantage head ...................... Wang et al., ICML 2016
* n-step returns .................................... Sutton 1988 (as in Rainbow, 2017)
* Huber loss, Adam (2014), gradient-norm clipping

Only PyTorch 1.0-era API is used (no AMP, no torch.compile, no MPS).
"""
import collections

import numpy as np
import torch
import torch.nn as nn


class DuelingQNetwork(nn.Module):
    """MLP torso + dueling head: Q(s, a) = V(s) + A(s, a) - mean_a A(s, a)."""

    def __init__(self, obs_dim, n_actions, hidden=256):
        super(DuelingQNetwork, self).__init__()
        self.obs_dim, self.n_actions, self.hidden = obs_dim, n_actions, hidden
        self.torso = nn.Sequential(
            nn.Linear(obs_dim, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden), nn.ReLU(),
        )
        self.value = nn.Sequential(nn.Linear(hidden, hidden // 2), nn.ReLU(),
                                   nn.Linear(hidden // 2, 1))
        self.advantage = nn.Sequential(nn.Linear(hidden, hidden // 2), nn.ReLU(),
                                       nn.Linear(hidden // 2, n_actions))

    def forward(self, x):
        h = self.torso(x)
        adv = self.advantage(h)
        return self.value(h) + adv - adv.mean(dim=1, keepdim=True)

    def layers(self):
        """Linear layers in evaluation order (used by the web exporter)."""
        return {
            "torso": [self.torso[0], self.torso[2]],
            "value": [self.value[0], self.value[2]],
            "advantage": [self.advantage[0], self.advantage[2]],
        }


class ReplayBuffer:
    """Preallocated ring buffer with uniform sampling."""

    def __init__(self, capacity, obs_dim, seed=0):
        self.capacity = capacity
        self.obs = np.zeros((capacity, obs_dim), np.float32)
        self.next_obs = np.zeros((capacity, obs_dim), np.float32)
        self.actions = np.zeros(capacity, np.int64)
        self.rewards = np.zeros(capacity, np.float32)
        self.discounts = np.zeros(capacity, np.float32)   # gamma^k, or 0 when terminal
        self.index = 0
        self.size = 0
        self.rng = np.random.RandomState(seed)

    def add(self, obs, action, reward, next_obs, discount):
        i = self.index
        self.obs[i] = obs
        self.actions[i] = action
        self.rewards[i] = reward
        self.next_obs[i] = next_obs
        self.discounts[i] = discount
        self.index = (i + 1) % self.capacity
        self.size = min(self.size + 1, self.capacity)

    def sample(self, batch_size):
        idx = self.rng.randint(0, self.size, size=batch_size)
        return (self.obs[idx], self.actions[idx], self.rewards[idx],
                self.next_obs[idx], self.discounts[idx])

    def __len__(self):
        return self.size


class NStepWriter:
    """Accumulates per-env 1-step transitions into n-step ones."""

    def __init__(self, n_envs, n, gamma, buffer):
        self.n, self.gamma, self.buffer = n, gamma, buffer
        self.queues = [collections.deque() for _ in range(n_envs)]

    def _flush_one(self, queue, next_obs, terminal):
        ret, discount = 0.0, 1.0
        for _, _, r in queue:
            ret += discount * r
            discount *= self.gamma
        obs, action, _ = queue.popleft()
        self.buffer.add(obs, action, ret, next_obs, 0.0 if terminal else discount)

    def add(self, env_index, obs, action, reward, next_obs, terminated, truncated):
        q = self.queues[env_index]
        q.append((obs, action, reward))
        if terminated or truncated:
            while q:
                self._flush_one(q, next_obs, terminated)
        elif len(q) == self.n:
            self._flush_one(q, next_obs, False)


def double_dqn_loss(online, target, batch):
    """Huber loss against the Double-DQN n-step target."""
    obs, actions, rewards, next_obs, discounts = batch
    q = online(obs).gather(1, actions.unsqueeze(1)).squeeze(1)
    with torch.no_grad():
        best = online(next_obs).argmax(dim=1, keepdim=True)
        next_q = target(next_obs).gather(1, best).squeeze(1)
        y = rewards + discounts * next_q
    return nn.functional.smooth_l1_loss(q, y)
