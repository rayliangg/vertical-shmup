"""小型的可重現亂數產生器（Marsaglia 的 xorshift32，2003）。

不用 `random.Random` 是為了讓 JavaScript 版（web/js/rng.js）
在同一個 seed 下產生完全一樣的亂數。
"""
import math

_MASK = 0xFFFFFFFF
_SCALE = 1.0 / 4294967296.0


class Rng:
    __slots__ = ("state",)

    def __init__(self, seed=1):
        self.seed(seed)

    def seed(self, seed):
        s = (int(seed) * 2654435761 + 0x9E3779B9) & _MASK   # 讓很小的 seed 也能打散
        self.state = s or 0x6D2B79F5

    def next_u32(self):
        x = self.state
        x ^= (x << 13) & _MASK
        x ^= x >> 17
        x ^= (x << 5) & _MASK
        self.state = x
        return x

    def random(self):
        """回傳 [0, 1) 之間的小數。"""
        return self.next_u32() * _SCALE

    def uniform(self, a, b):
        return a + (b - a) * self.random()

    def randint(self, a, b):
        """回傳 [a, b] 之間的整數（包含 a 和 b）。"""
        return a + int(math.floor(self.random() * (b - a + 1)))

    def chance(self, p):
        return self.random() < p

    def weighted(self, pairs):
        """從 ((key, 權重), ...) 依權重抽一個 key。"""
        total = 0
        for _, w in pairs:
            total += w
        r = self.random() * total
        for key, w in pairs:
            r -= w
            if r < 0:
                return key
        return pairs[-1][0]
