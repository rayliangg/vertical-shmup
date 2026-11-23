"""The whole game state and its fixed-timestep update. No pygame, no I/O.

`World.events` lists what happened during the last frame as
(name, x, y, value) tuples, consumed by the renderers (sound, particles)
and by the RL environment (rewards):

    shoot      player fired a volley                      value: power level
    explode    enemy destroyed                            value: enemy kind
    hit        enemy damaged but alive                    value: enemy kind
    hurt       player lost 1 HP                           value: HP left
    shield     shield absorbed a hit                      value: None
    bomb       bomb went off                              value: True if automatic
    cancel     enemy bullet erased (bomb / boss kill)     value: None
    graze      bullet brushed past the player             value: None
    pickup     item collected                             value: item kind
    warning    stage boss incoming                        value: stage
    boss       a boss finished its entrance               value: enemy kind
    phase      a boss started a new attack phase          value: (kind, phase 0-2)
    boss_down  stage boss destroyed, next stage begins    value: new stage
    escape     stage boss outlasted its last phase        value: new stage
    gameover   player has no HP left                      value: score
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
        self.bullets = []            # enemy bullets
        self.shots = []              # player shots
        self.items = []
        self.director = Director()
        self.events = []
        self.frame = 0
        self.stage = 1
        self.stage_frame = 0
        self.score = 0
        self.graze = 0
        self.done = False

    # -- derived values --------------------------------------------------
    @property
    def difficulty(self):
        progress = min(self.stage_frame / R.BOSS_TIME, 1.0)
        return 1.0 + R.DIFFICULTY_PER_STAGE * (self.stage - 1) + R.DIFFICULTY_IN_STAGE * progress

    @property
    def bullet_speed(self):
        return 0.85 + 0.15 * self.difficulty

    @property
    def boss(self):
        """The mid-boss or stage boss currently on screen, if any."""
        for e in self.enemies:
            if e.is_boss and e.alive:
                return e
        return None

    def emit(self, name, x, y, value=None):
        self.events.append((name, x, y, value))

    # -- main update -------------------------------------------------------
    def step(self, dx=0, dy=0, focus=False, bomb=False):
        """Advance one frame. dx, dy in {-1, 0, 1}. Returns HP lost this frame."""
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

    # -- combat ------------------------------------------------------------
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
            drops = R.MIDBOSS_ITEM_DROPS if e.kind == "midboss" else R.BOSS_ITEM_DROPS
            for _ in range(drops):
                x = e.x + rng.uniform(-60, 60)
                y = e.y + rng.uniform(-30, 30)
                self.items.append(Item(x, y, rng.weighted(ITEM_CHOICES)))
            self._cancel_bullets()
            if e.kind != "midboss":
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

    # -- bosses ------------------------------------------------------------
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
        self._next_stage()
        self.emit("escape", e.x, e.y, self.stage)

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
        """Resolve one hit. Returns HP actually lost (0 or 1)."""
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
