"""Tiny deterministic PRNG (Marsaglia's xorshift32, 2003).

The game uses this instead of `random.Random` so the JavaScript port
(web/js/rng.js) produces exactly the same numbers from the same seed.
"""
import math

_MASK = 0xFFFFFFFF
_SCALE = 1.0 / 4294967296.0


class Rng:
    __slots__ = ("state",)

    def __init__(self, seed=1):
        self.seed(seed)

    def seed(self, seed):
        s = (int(seed) * 2654435761 + 0x9E3779B9) & _MASK   # spread small seeds
        self.state = s or 0x6D2B79F5

    def next_u32(self):
        x = self.state
        x ^= (x << 13) & _MASK
        x ^= x >> 17
        x ^= (x << 5) & _MASK
        self.state = x
        return x

    def random(self):
        """Float in [0, 1)."""
        return self.next_u32() * _SCALE

    def uniform(self, a, b):
        return a + (b - a) * self.random()

    def randint(self, a, b):
        """Integer in [a, b], both inclusive."""
        return a + int(math.floor(self.random() * (b - a + 1)))

    def chance(self, p):
        return self.random() < p

    def weighted(self, pairs):
        """Pick a key from ((key, weight), ...)."""
        total = 0
        for _, w in pairs:
            total += w
        r = self.random() * total
        for key, w in pairs:
            r -= w
            if r < 0:
                return key
        return pairs[-1][0]
