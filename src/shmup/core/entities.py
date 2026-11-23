"""玩家、子彈、道具。只有資料和移動，不負責畫圖。"""
import math

from . import rules as R


class Player:
    __slots__ = ("x", "y", "hp", "bombs", "power", "shield", "invuln",
                 "fire_cooldown", "move_x", "focus")

    def __init__(self):
        self.x = R.WIDTH / 2
        self.y = R.PLAYER_START_Y
        self.hp = R.PLAYER_MAX_HP
        self.bombs = R.PLAYER_START_BOMBS
        self.power = 1
        self.shield = False
        self.invuln = 0
        self.fire_cooldown = 0
        self.move_x = 0              # 最後一次的左右輸入，用來畫機身傾斜
        self.focus = False

    def move(self, dx, dy, focus):
        speed = R.PLAYER_FOCUS_SPEED if focus else R.PLAYER_SPEED
        if dx and dy:
            speed *= R.DIAGONAL
        self.x = min(max(self.x + dx * speed, R.PLAYER_HALF_W), R.WIDTH - R.PLAYER_HALF_W)
        self.y = min(max(self.y + dy * speed, R.PLAYER_HALF_H), R.HEIGHT - R.PLAYER_HALF_H)
        self.move_x = dx
        self.focus = focus

    def shots(self):
        """依目前火力等級，產生一次射擊的所有子彈。"""
        x, y, s = self.x, self.y - R.PLAYER_HALF_H, R.SHOT_SPEED
        p = self.power
        if p == 1:
            return [Shot(x, y, 0.0, -s)]
        if p == 2:
            return [Shot(x - 8, y, 0.0, -s), Shot(x + 8, y, 0.0, -s)]
        if p == 3:
            return [Shot(x, y, 0.0, -s), Shot(x - 6, y, -1.6, -s), Shot(x + 6, y, 1.6, -s)]
        return [Shot(x - 8, y, 0.0, -s), Shot(x + 8, y, 0.0, -s),
                Shot(x - 10, y, -2.6, -s), Shot(x + 10, y, 2.6, -s),
                Shot(x, y - 6, 0.0, -s)]


class Shot:
    """玩家的子彈。"""
    __slots__ = ("x", "y", "vx", "vy", "alive")

    def __init__(self, x, y, vx, vy):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.alive = True

    def update(self):
        self.x += self.vx
        self.y += self.vy
        if self.y < -20 or self.x < -20 or self.x > R.WIDTH + 20:
            self.alive = False


class Bullet:
    """敵人的子彈：一個走直線的圓。"""
    __slots__ = ("x", "y", "vx", "vy", "r", "kind", "grazed", "alive")

    def __init__(self, x, y, vx, vy, kind="orb"):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.kind = kind
        self.r = R.BULLET_RADIUS[kind]
        self.grazed = False
        self.alive = True

    def update(self):
        self.x += self.vx
        self.y += self.vy
        m = R.BULLET_MARGIN
        if self.x < -m or self.x > R.WIDTH + m or self.y < -m or self.y > R.HEIGHT + m:
            self.alive = False


class Item:
    __slots__ = ("x", "y", "vy", "kind", "magnet", "alive", "age")

    def __init__(self, x, y, kind):
        self.x, self.y, self.kind = x, y, kind
        self.vy = R.ITEM_POP_SPEED
        self.magnet = False
        self.alive = True
        self.age = 0

    def update(self, player):
        self.age += 1
        dx, dy = player.x - self.x, player.y - self.y
        d2 = dx * dx + dy * dy
        if (not self.magnet and (player.y < R.COLLECT_LINE_Y
                                 or d2 < R.ITEM_MAGNET_RADIUS * R.ITEM_MAGNET_RADIUS)):
            self.magnet = True
        if self.magnet:
            d = math.sqrt(d2)
            if d > 1e-6:
                step = min(R.ITEM_MAGNET_SPEED, d)
                self.x += dx / d * step
                self.y += dy / d * step
        else:
            self.vy = min(self.vy + 0.08, R.ITEM_FALL_SPEED)
            self.y += self.vy
            if self.y > R.HEIGHT + 20:
                self.alive = False
