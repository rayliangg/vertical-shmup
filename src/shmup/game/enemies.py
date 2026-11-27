"""敵機、隕石、魔王。

所有敵人共用同一個資料類別，不同種類的行為寫成不同的 update 函式，
這樣比較好對照著寫 web/js/core.js。
"""
import math

from . import rules as R
from .entities import Bullet

HALF_PI = math.pi / 2
TAU = 2 * math.pi


# --- 彈幕的發射方式（所有敵人共用：自機狙、扇形、環形） ------------------------
def aim_angle(x, y, target):
    return math.atan2(target.y - y, target.x - x)


def single(out, x, y, angle, speed, kind="orb"):
    out.append(Bullet(x, y, math.cos(angle) * speed, math.sin(angle) * speed, kind))


def fan(out, x, y, angle, speed, count, spread, kind="orb"):
    """以 `angle` 為中心，在 `spread` 弧度內平均射出 `count` 顆。"""
    if count == 1:
        single(out, x, y, angle, speed, kind)
        return
    start = angle - spread / 2
    step = spread / (count - 1)
    for i in range(count):
        single(out, x, y, start + step * i, speed, kind)


def ring(out, x, y, count, speed, offset=0.0, kind="orb"):
    """一整圈平均射出 `count` 顆。"""
    step = TAU / count
    for i in range(count):
        single(out, x, y, offset + step * i, speed, kind)


class Enemy:
    __slots__ = ("kind", "x", "y", "vx", "vy", "hp", "max_hp", "radius", "score",
                 "drop", "age", "alive", "state", "timer", "fire_timer", "alt_timer",
                 "home_x", "amp", "phase", "target_y", "flash", "is_boss",
                 "phase_index", "phase_timer", "rage")

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
        self.flash = 0              # 被打到時閃白光的 frame 數（只是視覺效果）
        self.is_boss = spec.get("boss", False)
        self.phase_index = 0        # 魔王階段 0 / 1 / 2
        self.phase_timer = 0        # 目前這個階段已經過了幾個 frame
        self.rage = False           # 雙魔王的另一台被打倒後會暴走

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


# --- 各種敵人的行為 ----------------------------------------------------------
def _scout(e, w):
    e.x += e.vx
    e.y += e.vy
    if e.y > 0:
        e.fire_timer -= 1
        if e.fire_timer <= 0:
            a = aim_angle(e.x, e.y, w.player)
            single(w.bullets, e.x, e.y, a, 3.0 * w.bullet_speed)
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
            fan(w.bullets, e.x, e.y, HALF_PI, 2.6 * w.bullet_speed, 3, 0.5)
            e.fire_timer = interval(110, w.difficulty)
    if e.y > R.HEIGHT + 40:
        e.alive = False


def _diver(e, w):
    if e.state == 0:                      # 往下飛進場
        e.y += e.vy
        if e.y >= e.target_y:
            e.state, e.timer, e.vy = 1, 35, 0.0
    elif e.state == 1:                    # 鎖定玩家（畫面上會抖動提示）
        e.timer -= 1
        if e.timer <= 0:
            a = aim_angle(e.x, e.y, w.player)
            speed = 7.5 * w.bullet_speed
            e.vx, e.vy = math.cos(a) * speed, math.sin(a) * speed
            e.state = 2
    else:                                 # 衝刺
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
            ring(w.bullets, e.x, e.y, count, 2.2 * w.bullet_speed, e.age * 0.05)
            e.fire_timer = interval(80, w.difficulty)
        e.alt_timer -= 1
        if e.alt_timer <= 0:
            a = aim_angle(e.x, e.y, w.player)
            single(w.bullets, e.x, e.y, a, 5.5 * w.bullet_speed, "laser")
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


# --- 魔王 -------------------------------------------------------------------
ENTRY_Y = {"boss_warden": 130.0, "boss_fang": 120.0}


def _sway(e, center, amp, speed):
    """用 sin 波左右移動；順便更新 vx，讓 agent 知道它往哪邊動。"""
    e.phase += speed
    new_x = center + amp * math.sin(e.phase)
    e.vx = new_x - e.x
    e.x = new_x


def _boss_phases(e, w):
    """所有魔王共用的部分：進場、換階段、階段時間到。

    魔王還在進場（還不能開火）的時候回傳 False。
    """
    if e.state == 0:
        e.y += 1.5
        if e.y >= e.target_y:
            e.state = 1
            w.emit("boss", e.x, e.y, e.kind)
            w.emit("phase", e.x, e.y, (e.kind, 0))
        return False
    e.phase_timer += 1
    frac = e.hp / e.max_hp
    phase = 0 if frac > R.PHASE_THRESHOLDS[0] else (1 if frac > R.PHASE_THRESHOLDS[1] else 2)
    if phase != e.phase_index:
        w.boss_phase_change(e, phase, False)
    elif e.phase_timer >= R.BOSS_PHASE_TIME:
        if e.phase_index < 2:                       # 時間到：直接跳到下一個階段
            e.hp = int(math.floor(e.max_hp * R.PHASE_THRESHOLDS[e.phase_index]))
            w.boss_phase_change(e, e.phase_index + 1, True)
        else:
            w.boss_escaped(e)
            return False
    e.fire_timer -= 1
    e.alt_timer -= 1
    return True


def _warden(e, w):
    """第 1 關魔王：自機狙扇形 -> 雙螺旋 -> 密集環形彈。"""
    if not _boss_phases(e, w):
        return
    _sway(e, R.WIDTH / 2, 140, 0.012)
    bs, d = w.bullet_speed, w.difficulty
    if e.phase_index == 0:
        if e.fire_timer <= 0:
            a = aim_angle(e.x, e.y, w.player)
            fan(w.bullets, e.x, e.y + 30, a, 3.4 * bs, 5, 0.6)
            e.fire_timer = interval(50, d)
        if e.alt_timer <= 0:
            ring(w.bullets, e.x, e.y, 20, 1.9 * bs, e.amp, "big")
            e.amp += 0.3
            e.alt_timer = interval(130, d)
    elif e.phase_index == 1:
        if e.fire_timer <= 0:
            single(w.bullets, e.x, e.y, e.amp, 2.5 * bs)
            single(w.bullets, e.x, e.y, e.amp + math.pi, 2.5 * bs)
            e.amp += 0.22
            e.fire_timer = 5
        if e.alt_timer <= 0:
            a = aim_angle(e.x, e.y, w.player)
            fan(w.bullets, e.x, e.y + 30, a, 6.0 * bs, 3, 0.25, "laser")
            e.alt_timer = interval(90, d)
    else:
        if e.fire_timer <= 0:
            ring(w.bullets, e.x, e.y, 24, 2.4 * bs, e.amp)
            e.amp += 0.13
            e.fire_timer = interval(30, d)
        if e.alt_timer <= 0:
            a = aim_angle(e.x, e.y, w.player)
            single(w.bullets, e.x, e.y + 30, a, 4.2 * bs)
            e.alt_timer = 10


def _fang(e, w):
    """第 2 關（最後一關）的雙魔王（兩台一起出場）：交叉火力 -> 反向風車彈 -> 追著玩家跑。

    兩台各自有自己的 HP 和階段；其中一台被打倒後，另一台會暴走（射速變快）。
    """
    if not _boss_phases(e, w):
        return
    bs, d = w.bullet_speed * R.FANG_BULLET_SCALE, w.difficulty * R.FANG_FIRE_SCALE
    if e.rage:
        d = d * R.RAGE_SPEEDUP
    side = -1.0 if e.home_x < R.WIDTH / 2 else 1.0
    if e.phase_index < 2:
        _sway(e, e.home_x, 80, 0.02)
    else:                                            # Fang Rush：跟著玩家的 x 座標移動（兩台一左一右夾擊）
        e.vx = min(max(w.player.x + side * 60 - e.x, -3.0), 3.0)
        e.x += e.vx
    if e.phase_index == 0:
        if e.fire_timer <= 0:
            for side in (-1, 1):
                gx, gy = e.x + side * 50, e.y + 20
                a = aim_angle(gx, gy, w.player)
                fan(w.bullets, gx, gy, a, 5.5 * bs, 3, 0.2, "laser")
            e.fire_timer = interval(30, d)
        if e.alt_timer <= 0:
            ring(w.bullets, e.x, e.y, 12, 2.0 * bs, e.amp)
            e.amp += 0.25
            e.alt_timer = interval(60, d)
    elif e.phase_index == 1:
        if e.fire_timer <= 0:
            for k in range(4):
                single(w.bullets, e.x, e.y, e.amp + k * HALF_PI, 2.6 * bs)
                single(w.bullets, e.x, e.y, -e.amp + k * HALF_PI + 0.4, 2.2 * bs)
            e.amp += 0.17
            e.fire_timer = interval(24, d)
    else:
        if e.fire_timer <= 0:
            ring(w.bullets, e.x, e.y, 18, 2.0 * bs, e.amp, "big")
            e.amp += 0.17
            e.fire_timer = interval(45, d)
        if e.alt_timer <= 0:
            a = aim_angle(e.x, e.y, w.player)
            single(w.bullets, e.x, e.y + 30, a, 4.4 * bs)
            e.alt_timer = R.FANG_RUSH_SHOT_INTERVAL


UPDATERS = {
    "scout": _scout,
    "weaver": _weaver,
    "diver": _diver,
    "gunship": _gunship,
    "meteor_big": _meteor,
    "meteor_medium": _meteor,
    "meteor_small": _meteor,
    "boss_warden": _warden,
    "boss_fang": _fang,
}

SPLITS = {"meteor_big": "meteor_medium", "meteor_medium": "meteor_small"}
