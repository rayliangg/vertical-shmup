"""整個遊戲的狀態，以及固定時間步長的更新。不用 pygame，也不讀寫檔案。

`World.events` 記錄上一個 frame 發生了什麼事，每一筆是 (名稱, x, y, 值)，
畫面（音效、粒子特效）和 RL 環境（算獎勵）都會讀它：

    shoot      玩家射擊                          值：火力等級
    explode    敵人被打倒                        值：敵人種類
    hit        敵人被打到但還沒死                值：敵人種類
    hurt       玩家掉 1 滴血                     值：剩下的 HP
    shield     護盾擋掉一次攻擊                  值：None
    bomb       炸彈爆炸                          值：是否為自動炸彈
    cancel     敵彈被消掉（炸彈 / 打倒魔王）     值：None
    graze      子彈擦過玩家身邊                  值：None
    pickup     撿到道具                          值：道具種類
    warning    魔王快要出現                      值：關卡
    boss       魔王進場完畢                      值：敵人種類
    phase      魔王進入新的攻擊階段              值：(種類, 階段 0-2)
    boss_down  魔王被打倒，進入下一關            值：新的關卡
    escape     魔王撐過最後階段後逃走            值：新的關卡
    rage       雙魔王其中一台倒下，另一台暴走    值：敵人種類
    clear      最後一關結束，遊戲結束            值：是否打倒魔王（ALL CLEAR）
    gameover   玩家沒血了                        值：分數
"""
from . import rules as R
from .director import Director
from .enemies import SPLITS, Enemy
from .entities import Item, Player
from .rng import Rng

ITEM_CHOICES = tuple(zip(range(len(R.ITEM_WEIGHTS)), R.ITEM_WEIGHTS))


class World:
    def __init__(self, seed=0):
        self.rng = Rng(seed)
        self.reset(seed)

    def reset(self, seed=None):
        if seed is not None:
            self.rng.seed(seed)
        self.player = Player()
        self.enemies = []
        self.bullets = []            # 敵人的子彈
        self.shots = []              # 玩家的子彈
        self.items = []
        self.director = Director()
        self.events = []
        self.frame = 0
        self.stage = 1
        self.stage_frame = 0
        self.score = 0
        self.graze = 0
        self.done = False
        self.cleared = False         # 是否打倒最後一關的魔王（ALL CLEAR）

    # -- 推算出來的數值 --------------------------------------------------
    @property
    def difficulty(self):
        progress = min(self.stage_frame / R.BOSS_TIME, 1.0)
        return 1.0 + R.DIFFICULTY_PER_STAGE * (self.stage - 1) + R.DIFFICULTY_IN_STAGE * progress

    @property
    def bullet_speed(self):
        return 0.85 + 0.15 * self.difficulty

    @property
    def boss(self):
        """畫面上的中魔王或關卡魔王，沒有的話回傳 None。"""
        for e in self.enemies:
            if e.is_boss and e.alive:
                return e
        return None

    def emit(self, name, x, y, value=None):
        self.events.append((name, x, y, value))

    # -- 每個 frame 的更新 ------------------------------------------------
    def step(self, dx=0, dy=0, focus=False, bomb=False):
        """前進一個 frame。dx, dy 是 -1、0、1。回傳這個 frame 掉了幾滴血。"""
        if self.done:
            return 0
        self.events = []
        self.frame += 1
        self.stage_frame += 1
        p = self.player

        p.move(dx, dy, focus)
        if bomb and p.bombs > 0:
            self._bomb(auto=False)
        if p.invuln > 0:
            p.invuln -= 1
        p.fire_cooldown -= 1
        if p.fire_cooldown <= 0:
            self.shots.extend(p.shots())
            p.fire_cooldown = R.FIRE_INTERVAL
            self.emit("shoot", p.x, p.y, p.power)

        self.director.update(self)
        for e in list(self.enemies):
            if e.alive:
                e.update(self)
        for s in self.shots:
            s.update()
        for b in self.bullets:
            b.update()
        for it in self.items:
            it.update(p)

        self._shots_vs_enemies()
        lost = self._player_collisions()
        self._pickups()

        self.enemies = [e for e in self.enemies if e.alive]
        self.bullets = [b for b in self.bullets if b.alive]
        self.shots = [s for s in self.shots if s.alive]
        self.items = [i for i in self.items if i.alive]
        if p.hp <= 0:
            self.done = True
            self.emit("gameover", p.x, p.y, self.score)
        return lost

    # -- 戰鬥 --------------------------------------------------------------
    def _shots_vs_enemies(self):
        for s in self.shots:
            if not s.alive:
                continue
            for e in self.enemies:
                if not e.alive or not e.damageable:
                    continue
                dx, dy = e.x - s.x, e.y - s.y
                rr = e.radius + R.SHOT_RADIUS
                if dx * dx + dy * dy < rr * rr:
                    s.alive = False
                    self.damage_enemy(e, R.SHOT_DAMAGE)
                    break

    def damage_enemy(self, e, amount):
        e.hp -= amount
        e.flash = 3
        if e.hp > 0:
            self.emit("hit", e.x, e.y, e.kind)
            return
        e.alive = False
        self.score += e.score
        self.emit("explode", e.x, e.y, e.kind)
        rng = self.rng
        if e.is_boss:
            for _ in range(R.BOSS_ITEM_DROPS):
                x = e.x + rng.uniform(-60, 60)
                y = e.y + rng.uniform(-30, 30)
                self.items.append(Item(x, y, rng.weighted(ITEM_CHOICES)))
            self._cancel_bullets()
            if self._last_stage_boss(e):
                if self.stage >= R.FINAL_STAGE:
                    self._all_clear(e, True)
                else:
                    self._next_stage()
                    self.emit("boss_down", e.x, e.y, self.stage)
            return
        if e.drop > 0 and rng.chance(e.drop):
            self.items.append(Item(e.x, e.y, rng.weighted(ITEM_CHOICES)))
        child = SPLITS.get(e.kind)
        if child:
            for side in (-1, 1):
                self.enemies.append(Enemy(child, e.x + side * 10, e.y,
                                          side * 1.2 + e.vx * 0.5, e.vy))

    # -- 魔王 --------------------------------------------------------------
    def boss_phase_change(self, e, phase, timed_out):
        e.phase_index = phase
        e.phase_timer = 0
        e.fire_timer, e.alt_timer = 40, 70
        self._cancel_bullets()
        if not timed_out:
            self.score += R.PHASE_BONUS
        self.emit("phase", e.x, e.y, (e.kind, phase))

    def boss_escaped(self, e):
        e.alive = False
        self._cancel_bullets()
        if self._last_stage_boss(e):
            if self.stage >= R.FINAL_STAGE:
                self._all_clear(e, False)
            else:
                self._next_stage()
                self.emit("escape", e.x, e.y, self.stage)

    def _last_stage_boss(self, gone):
        """`gone` 是不是最後一台關卡魔王？不是的話，剩下的魔王會暴走。"""
        others = [o for o in self.enemies if o is not gone and o.alive and o.is_boss]
        for o in others:
            if not o.rage:
                o.rage = True
                self.emit("rage", o.x, o.y, o.kind)
        return not others

    def _all_clear(self, e, defeated):
        """最後一關的魔王都打倒（或逃走）了：遊戲結束。打倒的話有通關獎勵。"""
        if defeated:
            self.cleared = True
            self.score += R.CLEAR_BONUS + R.CLEAR_BONUS_PER_HP * self.player.hp
        self.done = True
        self.emit("clear", e.x, e.y, defeated)

    def _next_stage(self):
        self.stage += 1
        self.stage_frame = 0
        self.director.boss_defeated()

    def _player_collisions(self):
        p = self.player
        lost = 0
        for b in self.bullets:
            if not b.alive:
                continue
            dx, dy = b.x - p.x, b.y - p.y
            d2 = dx * dx + dy * dy
            rr = R.PLAYER_RADIUS + b.r
            if d2 < rr * rr:
                if p.invuln == 0:
                    b.alive = False
                    lost += self._hit_player()
            elif not b.grazed:
                gr = R.PLAYER_GRAZE_RADIUS + b.r
                if d2 < gr * gr:
                    b.grazed = True
                    self.graze += 1
                    self.score += R.GRAZE_SCORE
                    self.emit("graze", b.x, b.y)
        for e in self.enemies:
            if not e.alive:
                continue
            dx, dy = e.x - p.x, e.y - p.y
            rr = R.PLAYER_RADIUS + e.radius * R.ENEMY_CONTACT_SCALE
            if dx * dx + dy * dy < rr * rr and p.invuln == 0:
                if not e.is_boss:
                    self.damage_enemy(e, R.CONTACT_DAMAGE_TO_ENEMY)
                lost += self._hit_player()
        return lost

    def _hit_player(self):
        """處理一次被打中。回傳實際掉的血（0 或 1）。"""
        p = self.player
        if p.invuln > 0:
            return 0
        if p.shield:
            p.shield = False
            p.invuln = R.SHIELD_INVULN_FRAMES
            self._cancel_bullets(radius=90.0)
            self.emit("shield", p.x, p.y)
            return 0
        if R.AUTO_BOMB and p.bombs > 0:
            self._bomb(auto=True)
            return 0
        p.hp -= 1
        p.power = max(1, p.power - 1)
        p.invuln = R.INVULN_FRAMES
        self.emit("hurt", p.x, p.y, p.hp)
        return 1

    def _bomb(self, auto):
        p = self.player
        p.bombs -= 1
        p.invuln = max(p.invuln, R.BOMB_INVULN_FRAMES)
        self.emit("bomb", p.x, p.y, auto)
        self._cancel_bullets()
        for e in list(self.enemies):
            if e.alive and e.damageable:
                self.damage_enemy(e, R.BOMB_DAMAGE)

    def _cancel_bullets(self, radius=None):
        p = self.player
        for b in self.bullets:
            if not b.alive:
                continue
            if radius is not None:
                dx, dy = b.x - p.x, b.y - p.y
                if dx * dx + dy * dy > radius * radius:
                    continue
            b.alive = False
            self.score += R.BULLET_CANCEL_SCORE
            self.emit("cancel", b.x, b.y)

    def _pickups(self):
        p = self.player
        rr = R.ITEM_PICKUP_RADIUS * R.ITEM_PICKUP_RADIUS
        for it in self.items:
            if not it.alive:
                continue
            dx, dy = it.x - p.x, it.y - p.y
            if dx * dx + dy * dy >= rr:
                continue
            it.alive = False
            k = it.kind
            if k == R.ITEM_POWER:
                if p.power < R.PLAYER_MAX_POWER:
                    p.power += 1
                else:
                    self.score += 200
            elif k == R.ITEM_HEAL:
                p.hp = min(p.hp + 1, R.PLAYER_MAX_HP)
            elif k == R.ITEM_SHIELD:
                p.shield = True
            elif k == R.ITEM_BOMB:
                p.bombs = min(p.bombs + 1, R.PLAYER_MAX_BOMBS)
            else:
                self.score += R.ITEM_SCORE_VALUE
            self.emit("pickup", it.x, it.y, k)
