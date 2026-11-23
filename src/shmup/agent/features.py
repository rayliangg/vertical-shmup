"""Turn a World into the fixed-size vector the Q-network reads.

Mirrored exactly by web/js/features.js (tests/test_web_parity.py checks it).

Layout (OBS_DIM = 284 floats):
    player      7   x, y, hp, bombs, power, shield, invulnerability
    bullets   120   24 nearest enemy bullets x (dx, dy, vx, vy, radius)
    enemies    64   8 nearest enemies x (dx, dy, vx, vy, radius, hp, is_boss, present)
    danger     81   9x9 grid around the player: how soon a bullet will be there
    items       8   2 nearest items x (dx, dy, kind, present)
    boss        4   present, dx, dy, hp
"""
import math

from ..core import rules as R

# action index -> (dx, dy, focus)
_DIRS = ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1))
ACTIONS = tuple((dx, dy, focus) for focus in (False, True) for dx, dy in _DIRS)
N_ACTIONS = len(ACTIONS)

N_BULLETS = 24
N_ENEMIES = 8
N_ITEMS = 2
GRID = 9
CELL = 28.0
LOOKAHEAD = ((0, 1.0), (6, 0.75), (12, 0.5), (18, 0.25))   # (frames ahead, weight)

POS_X = 240.0
POS_Y = 360.0
VEL = 6.0

OFF_PLAYER = 0
OFF_BULLETS = 7
OFF_ENEMIES = OFF_BULLETS + N_BULLETS * 5
OFF_GRID = OFF_ENEMIES + N_ENEMIES * 8
OFF_ITEMS = OFF_GRID + GRID * GRID
OFF_BOSS = OFF_ITEMS + N_ITEMS * 4
OBS_DIM = OFF_BOSS + 4


def _nearest(things, px, py, k):
    """k nearest by squared distance; ties broken by list index (stable in JS too)."""
    scored = []
    for i, t in enumerate(things):
        if t.alive:
            dx, dy = t.x - px, t.y - py
            scored.append((dx * dx + dy * dy, i, t))
    scored.sort(key=lambda s: (s[0], s[1]))
    return [s[2] for s in scored[:k]]


def observe(world, out=None):
    """Return a list of OBS_DIM floats (or fill `out`, any mutable sequence)."""
    o = [0.0] * OBS_DIM if out is None else out
    if out is not None:
        for i in range(OBS_DIM):
            o[i] = 0.0
    p = world.player
    px, py = p.x, p.y

    o[0] = px / R.WIDTH * 2 - 1
    o[1] = py / R.HEIGHT * 2 - 1
    o[2] = p.hp / R.PLAYER_MAX_HP
    o[3] = p.bombs / R.PLAYER_MAX_BOMBS
    o[4] = (p.power - 1) / (R.PLAYER_MAX_POWER - 1)
    o[5] = 1.0 if p.shield else 0.0
    o[6] = p.invuln / R.INVULN_FRAMES

    j = OFF_BULLETS
    for b in _nearest(world.bullets, px, py, N_BULLETS):
        o[j] = (b.x - px) / POS_X
        o[j + 1] = (b.y - py) / POS_Y
        o[j + 2] = b.vx / VEL
        o[j + 3] = b.vy / VEL
        o[j + 4] = b.r / 10.0
        j += 5

    j = OFF_ENEMIES
    for e in _nearest(world.enemies, px, py, N_ENEMIES):
        o[j] = (e.x - px) / POS_X
        o[j + 1] = (e.y - py) / POS_Y
        o[j + 2] = e.vx / VEL
        o[j + 3] = e.vy / VEL
        o[j + 4] = e.radius / 50.0
        o[j + 5] = e.hp / e.max_hp
        o[j + 6] = 1.0 if e.is_boss else 0.0
        o[j + 7] = 1.0
        j += 8

    _danger_grid(world, px, py, o)

    j = OFF_ITEMS
    for it in _nearest(world.items, px, py, N_ITEMS):
        o[j] = (it.x - px) / POS_X
        o[j + 1] = (it.y - py) / POS_Y
        o[j + 2] = it.kind / 4.0
        o[j + 3] = 1.0
        j += 4

    boss = world.boss
    if boss is not None:
        o[OFF_BOSS] = 1.0
        o[OFF_BOSS + 1] = (boss.x - px) / POS_X
        o[OFF_BOSS + 2] = (boss.y - py) / POS_Y
        o[OFF_BOSS + 3] = boss.hp / boss.max_hp
    return o


def _mark(o, gx, gy, weight):
    if 0 <= gx < GRID and 0 <= gy < GRID:
        k = OFF_GRID + gy * GRID + gx
        if weight > o[k]:
            o[k] = weight


def _danger_grid(world, px, py, o):
    half = GRID / 2.0
    for b in world.bullets:
        if not b.alive:
            continue
        for t, weight in LOOKAHEAD:
            gx = int(math.floor((b.x + b.vx * t - px) / CELL + half))
            gy = int(math.floor((b.y + b.vy * t - py) / CELL + half))
            _mark(o, gx, gy, weight)
    for e in world.enemies:                      # bodies: every cell they overlap now
        if not e.alive:
            continue
        r = e.radius * R.ENEMY_CONTACT_SCALE
        x0 = int(math.floor((e.x - r - px) / CELL + half))
        x1 = int(math.floor((e.x + r - px) / CELL + half))
        y0 = int(math.floor((e.y - r - py) / CELL + half))
        y1 = int(math.floor((e.y + r - py) / CELL + half))
        if x1 < 0 or y1 < 0 or x0 >= GRID or y0 >= GRID:
            continue
        for gy in range(max(y0, 0), min(y1, GRID - 1) + 1):
            for gx in range(max(x0, 0), min(x1, GRID - 1) + 1):
                _mark(o, gx, gy, 1.0)
