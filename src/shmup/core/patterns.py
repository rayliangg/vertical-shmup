"""所有敵人共用的發射方式（彈幕遊戲最基本的幾種）。"""
import math

from .entities import Bullet

TAU = 2 * math.pi


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
