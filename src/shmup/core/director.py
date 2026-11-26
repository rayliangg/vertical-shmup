"""決定什麼時候出什麼敵人。

一關的流程：雜魚波次（約 60 秒）-> WARNING -> 魔王。
第 1 關 Warden、第 2 關 Hive Carrier、第 3 關（最後一關）兩隻 Twin Fang。
"""
import math

from . import rules as R
from .enemies import ENTRY_Y, Enemy

IDLE, WARNING, BOSS_FIGHT = 0, 1, 2


class Director:
    __slots__ = ("state", "wave_timer", "warn_timer")

    def __init__(self):
        self.state = IDLE
        self.wave_timer = 90
        self.warn_timer = 0

    def update(self, w):
        if self.state == IDLE:
            if w.stage_frame >= R.BOSS_TIME:
                self.state = WARNING
                self.warn_timer = R.BOSS_WARNING_FRAMES
                w.emit("warning", R.WIDTH / 2, R.HEIGHT / 2, w.stage)
                return
            self.wave_timer -= 1
            if self.wave_timer <= 0:
                self.spawn_wave(w)
                base = max(R.WAVE_INTERVAL_MIN, R.WAVE_INTERVAL_START / w.difficulty)
                self.wave_timer = int(math.floor(base * w.rng.uniform(0.8, 1.2)))
        elif self.state == WARNING:
            self.warn_timer -= 1
            if self.warn_timer <= 0:
                kind = R.BOSS_ORDER[min(w.stage, R.FINAL_STAGE) - 1]
                if R.BOSS_COUNT.get(kind, 1) == 2:        # 雙魔王：一左一右
                    w.enemies.append(self._boss(w, kind, R.WIDTH / 2 - R.TWIN_OFFSET))
                    w.enemies.append(self._boss(w, kind, R.WIDTH / 2 + R.TWIN_OFFSET))
                else:
                    w.enemies.append(self._boss(w, kind, R.WIDTH / 2))
                self.state = BOSS_FIGHT

    @staticmethod
    def _boss(w, kind, x):
        hp = int(math.floor(R.ENEMIES[kind]["hp"] * (1 + R.BOSS_HP_PER_STAGE * (w.stage - 1))))
        e = Enemy(kind, x, -60.0, hp=hp)
        e.home_x = x
        e.target_y = ENTRY_Y[kind]
        e.fire_timer, e.alt_timer = 40, 70
        return e

    def boss_defeated(self):
        """魔王被打倒或逃走：開始下一關。"""
        self.state = IDLE
        self.wave_timer = 150

    # -- 雜魚波次 ----------------------------------------------------------
    def spawn_wave(self, w):
        allow_gunship = w.stage > 1 or w.stage_frame > R.GUNSHIP_AFTER
        choices = tuple(p for p in R.WAVES if p[0] != "gunship" or allow_gunship)
        getattr(self, "_" + w.rng.weighted(choices))(w)

    def _scout_line(self, w):
        rng, out = w.rng, w.enemies
        n = 3 + rng.randint(0, 2)
        spacing = R.WIDTH / (n + 1)
        for i in range(n):
            e = Enemy("scout", spacing * (i + 1), -30.0 - 20 * i, 0.0, 2.2)
            e.fire_timer = rng.randint(30, 90)
            out.append(e)

    def _scout_vee(self, w):
        rng, out = w.rng, w.enemies
        cx = rng.uniform(140, R.WIDTH - 140)
        for i in range(-2, 3):
            e = Enemy("scout", cx + i * 45, -30.0 - abs(i) * 35, 0.0, 2.4)
            e.fire_timer = rng.randint(30, 90)
            out.append(e)

    def _weavers(self, w):
        rng, out = w.rng, w.enemies
        amp = rng.uniform(50, 90)
        for side in (-1, 1):
            e = Enemy("weaver", 0.0, -30.0, 0.0, 1.6)
            e.home_x = R.WIDTH / 2 + side * rng.uniform(70, 150)
            e.amp = amp
            e.phase = 0.0 if side < 0 else math.pi
            e.x = e.home_x + amp * math.sin(e.phase)
            e.fire_timer = rng.randint(40, 100)
            out.append(e)

    def _divers(self, w):
        rng, out = w.rng, w.enemies
        for i in range(rng.randint(2, 3)):
            e = Enemy("diver", rng.uniform(60, R.WIDTH - 60), -30.0 - 40 * i, 0.0, 3.0)
            e.target_y = rng.uniform(70, 200)
            out.append(e)

    def _meteors(self, w):
        rng, out = w.rng, w.enemies
        for _ in range(rng.randint(2, 4)):
            kind = "meteor_big" if rng.chance(0.4) else "meteor_medium"
            x = rng.uniform(40, R.WIDTH - 40)
            y = -40 - rng.uniform(0, 80)
            vx = rng.uniform(-1.2, 1.2)
            vy = rng.uniform(1.5, 3.0)
            out.append(Enemy(kind, x, y, vx, vy))

    def _gunship(self, w):
        rng = w.rng
        e = Enemy("gunship", rng.uniform(100, R.WIDTH - 100), -40.0, 0.0, 1.5)
        e.target_y = rng.uniform(110, 210)
        e.fire_timer = 60
        e.alt_timer = 40
        w.enemies.append(e)
