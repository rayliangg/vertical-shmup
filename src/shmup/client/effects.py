"""Purely cosmetic effects: starfield, particles, shockwaves, score pop-ups.

Uses its own `random.Random`, never the game RNG, so effects can't change
the simulation.
"""
import math
import random

import pygame

from ..core import rules as R


class Starfield:
    """Two layers of drifting stars over a tiled, scrolling background."""
    LAYERS = ((60, 1.2, 1, 120), (35, 2.6, 2, 200))     # (count, speed, size, alpha)

    def __init__(self, rng):
        self.stars = []
        for count, speed, size, alpha in self.LAYERS:
            for _ in range(count):
                self.stars.append([rng.uniform(0, R.WIDTH), rng.uniform(0, R.HEIGHT),
                                   speed * rng.uniform(0.8, 1.2), size, alpha])
        self.rng = rng
        self.scroll = 0.0

    def update(self, boost=1.0):
        self.scroll = (self.scroll + 0.6 * boost) % 256
        for s in self.stars:
            s[1] += s[2] * boost
            if s[1] > R.HEIGHT:
                s[0], s[1] = self.rng.uniform(0, R.WIDTH), -2

    def draw(self, surf, tile):
        h = tile.get_height()
        y = int(self.scroll) - h
        while y < R.HEIGHT:
            x = 0
            while x < R.WIDTH:
                surf.blit(tile, (x, y))
                x += tile.get_width()
            y += h
        for x, y, _, size, alpha in self.stars:
            c = (alpha, alpha, min(255, alpha + 40))
            if size == 1:
                surf.set_at((int(x), int(y)), c)
            else:
                pygame.draw.rect(surf, c, (int(x), int(y), size, size + 1))


class Effects:
    MAX_PARTICLES = 600

    def __init__(self):
        self.rng = random.Random()
        self.particles = []      # [x, y, vx, vy, life, max_life, size, color, drag]
        self.rings = []          # [x, y, radius, speed, life, max_life, color, width]
        self.popups = []         # [surface, x, y, life]
        self.shake = 0.0
        self.flash = 0           # full-screen white flash frames
        self.starfield = Starfield(self.rng)

    def clear(self):
        del self.particles[:]
        del self.rings[:]
        del self.popups[:]
        self.shake = 0.0
        self.flash = 0

    # -- emitters ------------------------------------------------------------
    def sparks(self, x, y, color, count=8, speed=4.0, life=18, size=3, drag=0.9):
        r = self.rng
        for _ in range(count):
            if len(self.particles) >= self.MAX_PARTICLES:
                return
            a, s = r.uniform(0, 2 * math.pi), r.uniform(0.3, 1.0) * speed
            n = r.randint(int(life * 0.6), life)
            self.particles.append([x, y, math.cos(a) * s, math.sin(a) * s, n, n,
                                   size, color, drag])

    def ring(self, x, y, color, speed=4.0, life=18, width=3, radius=4.0):
        self.rings.append([x, y, radius, speed, life, life, color, width])

    def explosion(self, x, y, big=False):
        scale = 2.2 if big else 1.0
        self.ring(x, y, (255, 220, 160), 5.0 * scale, int(18 * scale), 3)
        self.sparks(x, y, (255, 200, 80), int(16 * scale), 5.0 * scale, int(28 * scale), 3)
        self.sparks(x, y, (255, 90, 40), int(10 * scale), 3.0 * scale, int(36 * scale), 4)
        self.sparks(x, y, (255, 255, 255), int(6 * scale), 7.0 * scale, 12, 2)
        self.shake = max(self.shake, 9.0 if big else 2.5)
        if big:
            self.flash = 10

    def popup(self, surface, x, y):
        self.popups.append([surface, x, y, 50])

    # -- update / draw ------------------------------------------------------
    def update(self):
        alive = []
        for p in self.particles:
            p[4] -= 1
            if p[4] > 0:
                p[2] *= p[8]
                p[3] *= p[8]
                p[0] += p[2]
                p[1] += p[3]
                alive.append(p)
        self.particles = alive
        rings = []
        for g in self.rings:
            g[4] -= 1
            if g[4] > 0:
                g[2] += g[3]
                rings.append(g)
        self.rings = rings
        for t in self.popups:
            t[2] -= 0.8
            t[3] -= 1
        self.popups = [t for t in self.popups if t[3] > 0]
        self.shake *= 0.85
        if self.shake < 0.3:
            self.shake = 0.0
        if self.flash:
            self.flash -= 1

    def draw(self, surf):
        for x, y, _, _, life, max_life, size, color, _ in self.particles:
            k = life / float(max_life)
            s = max(1, int(size * (0.4 + 0.6 * k)))
            c = (int(color[0] * k + 40 * (1 - k)), int(color[1] * k), int(color[2] * k))
            pygame.draw.rect(surf, c, (int(x - s / 2), int(y - s / 2), s, s))
        for x, y, radius, _, life, max_life, color, width in self.rings:
            k = life / float(max_life)
            c = tuple(int(v * k) for v in color)
            pygame.draw.circle(surf, c, (int(x), int(y)), int(radius), max(1, int(width * k)))
        for img, x, y, life in self.popups:
            img.set_alpha(min(255, life * 8))
            surf.blit(img, img.get_rect(center=(int(x), int(y))))

    def offset(self):
        if not self.shake:
            return 0, 0
        s = self.shake
        return int(self.rng.uniform(-s, s)), int(self.rng.uniform(-s, s))
