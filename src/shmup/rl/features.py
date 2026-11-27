"""把 World 轉成 PPO 策略網路要吃的固定長度向量。

web/js/agent.js 裡的 observe() 是逐行對應的 JavaScript 版本，改這裡時兩邊要一起改。

排列方式（OBS_DIM = 290 個數字）：
    自機        7   x, y, HP, 炸彈, 火力, 護盾, 無敵時間
    子彈      120   最近 24 顆敵彈 x (dx, dy, vx, vy, 半徑)
    敵人       64   最近 8 個敵人 x (dx, dy, vx, vy, 半徑, HP, 是否魔王, 存在)
    危險格     81   自機周圍 9x9 的格子：子彈多快會到那一格
    道具        8   最近 2 個道具 x (dx, dy, 種類, 存在)
    魔王       10   最多 2 隻 x (存在, dx, dy, HP, 是否暴走)；第 2 關的 TWIN FANG 有兩隻
"""
import math

from ..game import rules as R

# 動作編號 -> (dx, dy, 是否慢速)
_DIRS = ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1))
ACTIONS = tuple((dx, dy, focus) for focus in (False, True) for dx, dy in _DIRS)
N_ACTIONS = len(ACTIONS)

N_BULLETS = 24
N_ENEMIES = 8
N_ITEMS = 2
N_BOSSES = 2
GRID = 9
CELL = 28.0
LOOKAHEAD = ((0, 1.0), (6, 0.75), (12, 0.5), (18, 0.25))   # (往後預測幾個 frame, 權重)

POS_X = 240.0
POS_Y = 360.0
VEL = 6.0

OFF_PLAYER = 0
OFF_BULLETS = 7
OFF_ENEMIES = OFF_BULLETS + N_BULLETS * 5
OFF_GRID = OFF_ENEMIES + N_ENEMIES * 8
OFF_ITEMS = OFF_GRID + GRID * GRID
OFF_BOSS = OFF_ITEMS + N_ITEMS * 4
OBS_DIM = OFF_BOSS + N_BOSSES * 5


def _nearest(things, px, py, k):
    """依距離平方取最近的 k 個；距離一樣時用 list 的順序決定（JS 那邊也一樣）。"""
    scored = []
    for i, t in enumerate(things):
        if t.alive:
            dx, dy = t.x - px, t.y - py
            scored.append((dx * dx + dy * dy, i, t))
    scored.sort(key=lambda s: (s[0], s[1]))
    return [s[2] for s in scored[:k]]


def observe(world, out=None):
    """回傳長度 OBS_DIM 的 list（或是直接填進 `out`）。"""
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

    j = OFF_BOSS                                 # 依出場順序（左邊那台先），不是依距離
    for e in [e for e in world.enemies if e.is_boss and e.alive][:N_BOSSES]:
        o[j] = 1.0
        o[j + 1] = (e.x - px) / POS_X
        o[j + 2] = (e.y - py) / POS_Y
        o[j + 3] = e.hp / e.max_hp
        o[j + 4] = 1.0 if e.rage else 0.0
        j += 5
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
    for e in world.enemies:                      # 敵人本體：現在蓋到的每一格都算危險
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
