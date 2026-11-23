"""DQN 的各個零件，只使用 2019 年以前發表的方法。

* Deep Q-Network、經驗回放、目標網路 ......... Mnih et al., Nature 2015
* Double DQN 目標 ............................ van Hasselt et al., AAAI 2016
* Dueling（V / A 分開的輸出頭） .............. Wang et al., ICML 2016
* n-step return .............................. Sutton 1988（Rainbow 2017 也有用）
* Huber loss、Adam（2014）、梯度裁剪

只用 PyTorch 1.0 時代就有的 API（沒有 AMP、torch.compile、MPS）。
"""
import collections

import numpy as np
import torch
import torch.nn as nn


class DuelingQNetwork(nn.Module):
    """MLP 主幹 + dueling 輸出頭：Q(s, a) = V(s) + A(s, a) - mean_a A(s, a)。"""

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
        """依計算順序回傳各個 Linear 層（匯出網頁版時用）。"""
        return {
            "torso": [self.torso[0], self.torso[2]],
            "value": [self.value[0], self.value[2]],
            "advantage": [self.advantage[0], self.advantage[2]],
        }


class ReplayBuffer:
    """事先配置好記憶體的環形 buffer，均勻隨機抽樣。"""

    def __init__(self, capacity, obs_dim, seed=0):
        self.capacity = capacity
        self.obs = np.zeros((capacity, obs_dim), np.float32)
        self.next_obs = np.zeros((capacity, obs_dim), np.float32)
        self.actions = np.zeros(capacity, np.int64)
        self.rewards = np.zeros(capacity, np.float32)
        self.discounts = np.zeros(capacity, np.float32)   # gamma^k；真正死亡時是 0
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
    """把每個環境的 1-step transition 累積成 n-step transition。"""

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
    """對 Double DQN 的 n-step 目標算 Huber loss。"""
    obs, actions, rewards, next_obs, discounts = batch
    q = online(obs).gather(1, actions.unsqueeze(1)).squeeze(1)
    with torch.no_grad():
        best = online(next_obs).argmax(dim=1, keepdim=True)
        next_q = target(next_obs).gather(1, best).squeeze(1)
        y = rewards + discounts * next_q
    return nn.functional.smooth_l1_loss(q, y)
