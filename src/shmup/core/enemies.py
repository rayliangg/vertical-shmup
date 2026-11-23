"""Enemy ships, meteors and the boss.

All enemies share one data class; the behaviour is a per-kind update
function. This keeps the code easy to mirror in web/js/core.js.
"""
import math

from . import patterns
from . import rules as R

HALF_PI = math.pi / 2


class Enemy:
    __slots__ = ("kind", "x", "y", "vx", "vy", "hp", "max_hp", "radius", "score",
                 "drop", "age", "alive", "state", "timer", "fire_timer", "alt_timer",
                 "home_x", "amp", "phase", "target_y", "flash")

    def __init__(self, kind, x, y, vx=0.0, vy=0.0, hp=None):
        spec = R.ENEMIES[kind]
        self.kind = kind
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.hp = self.max_hp = spec["hp"] if hp is None else hp
        self.radius = spec["radius"]
        self.score = spec["score"]
        self.drop = spec["drop"]
        self.age = 0
        self.alive = True
        self.state = 0
        self.timer = 0
        self.fire_timer = 60
        self.alt_timer = 60
        self.home_x = x
        self.amp = 0.0
        self.phase = 0.0
        self.target_y = 0.0
        self.flash = 0              # frames of white hit-flash (cosmetic)

    @property
    def is_boss(self):
        return self.kind == "boss"

    @property
    def damageable(self):
        return self.y > 10

    def update(self, world):
        self.age += 1
        if self.flash:
            self.flash -= 1
        UPDATERS[self.kind](self, world)


def interval(base, difficulty):
    return max(4, int(math.floor(base / difficulty)))


def _offscreen(e, margin=60.0):
    return (e.y > R.HEIGHT + margin or e.y < -margin - 40
            or e.x < -margin or e.x > R.WIDTH + margin)


# --- behaviours -------------------------------------------------------------
def _scout(e, w):
    e.x += e.vx
    e.y += e.vy
    if e.y > 0:
        e.fire_timer -= 1
        if e.fire_timer <= 0:
            a = patterns.aim_angle(e.x, e.y, w.player)
            patterns.single(w.bullets, e.x, e.y, a, 3.0 * w.bullet_speed)
            e.fire_timer = interval(90, w.difficulty)
    if e.y > R.HEIGHT + 40:
        e.alive = False


def _weaver(e, w):
    new_x = e.home_x + e.amp * math.sin(e.age * 0.03 + e.phase)
    e.vx = new_x - e.x
    e.x = new_x
    e.y += e.vy
    if e.y > 0:
        e.fire_timer -= 1
        if e.fire_timer <= 0:
            patterns.fan(w.bullets, e.x, e.y, HALF_PI, 2.6 * w.bullet_speed, 3, 0.5)
            e.fire_timer = interval(110, w.difficulty)
    if e.y > R.HEIGHT + 40:
        e.alive = False


def _diver(e, w):
    if e.state == 0:                      # drop in
        e.y += e.vy
        if e.y >= e.target_y:
            e.state, e.timer, e.vy = 1, 35, 0.0
    elif e.state == 1:                    # lock on (the renderer shakes it)
        e.timer -= 1
        if e.timer <= 0:
            a = patterns.aim_angle(e.x, e.y, w.player)
            speed = 7.5 * w.bullet_speed
            e.vx, e.vy = math.cos(a) * speed, math.sin(a) * speed
            e.state = 2
    else:                                 # dash
        e.x += e.vx
        e.y += e.vy
        if _offscreen(e):
            e.alive = False


def _gunship(e, w):
    if e.state == 0:
        e.y += e.vy
        if e.y >= e.target_y:
            e.state, e.timer, e.vy = 1, 300, 0.0
    elif e.state == 1:
        e.vx = math.sin(e.age * 0.02) * 0.8
        e.x += e.vx
        e.fire_timer -= 1
        if e.fire_timer <= 0:
            count = 10 + 2 * min(w.stage - 1, 4)
            patterns.ring(w.bullets, e.x, e.y, count, 2.2 * w.bullet_speed, e.age * 0.05)
            e.fire_timer = interval(80, w.difficulty)
        e.alt_timer -= 1
        if e.alt_timer <= 0:
            a = patterns.aim_angle(e.x, e.y, w.player)
            patterns.single(w.bullets, e.x, e.y, a, 5.5 * w.bullet_speed, "laser")
            e.alt_timer = interval(55, w.difficulty)
        e.timer -= 1
        if e.timer <= 0:
            e.state, e.vx, e.vy = 2, 0.0, -1.2
    else:
        e.y += e.vy
        if e.y < -60:
            e.alive = False


def _meteor(e, w):
    e.x += e.vx
    e.y += e.vy
    if _offscreen(e):
        e.alive = False


def _boss(e, w):
    if e.state == 0:                      # entrance
        e.y += 1.5
        if e.y >= 130:
            e.state = 1
        return
    e.phase += 0.012
    new_x = R.WIDTH / 2 + 140 * math.sin(e.phase)
    e.vx = new_x - e.x
    e.x = new_x
    bs, d = w.bullet_speed, w.difficulty
    frac = e.hp / e.max_hp
    e.fire_timer -= 1
    e.alt_timer -= 1
    if frac > 0.66:                       # phase 1: aimed fans + slow rings
        if e.fire_timer <= 0:
            a = patterns.aim_angle(e.x, e.y, w.player)
            patterns.fan(w.bullets, e.x, e.y + 30, a, 3.4 * bs, 5, 0.6)
            e.fire_timer = interval(50, d)
        if e.alt_timer <= 0:
            patterns.ring(w.bullets, e.x, e.y, 20, 1.9 * bs, e.amp, "big")
            e.amp += 0.3
            e.alt_timer = interval(130, d)
    elif frac > 0.33:                     # phase 2: double spiral + laser fans
        if e.fire_timer <= 0:
            patterns.single(w.bullets, e.x, e.y, e.amp, 2.5 * bs)
            patterns.single(w.bullets, e.x, e.y, e.amp + math.pi, 2.5 * bs)
            e.amp += 0.22
            e.fire_timer = 5
        if e.alt_timer <= 0:
            a = patterns.aim_angle(e.x, e.y, w.player)
            patterns.fan(w.bullets, e.x, e.y + 30, a, 6.0 * bs, 3, 0.25, "laser")
            e.alt_timer = interval(90, d)
    else:                                 # phase 3: dense rings + aimed stream
        if e.fire_timer <= 0:
            patterns.ring(w.bullets, e.x, e.y, 24, 2.4 * bs, e.amp)
            e.amp += 0.13
            e.fire_timer = interval(30, d)
        if e.alt_timer <= 0:
            a = patterns.aim_angle(e.x, e.y, w.player)
            patterns.single(w.bullets, e.x, e.y + 30, a, 4.2 * bs)
            e.alt_timer = 10


UPDATERS = {
    "scout": _scout,
    "weaver": _weaver,
    "diver": _diver,
    "gunship": _gunship,
    "meteor_big": _meteor,
    "meteor_medium": _meteor,
    "meteor_small": _meteor,
    "boss": _boss,
}

SPLITS = {"meteor_big": "meteor_medium", "meteor_medium": "meteor_small"}
