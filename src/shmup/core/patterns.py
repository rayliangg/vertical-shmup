"""Bullet emission patterns shared by all enemies (classic danmaku building blocks)."""
import math

from .entities import Bullet

TAU = 2 * math.pi


def aim_angle(x, y, target):
    return math.atan2(target.y - y, target.x - x)


def single(out, x, y, angle, speed, kind="orb"):
    out.append(Bullet(x, y, math.cos(angle) * speed, math.sin(angle) * speed, kind))


def fan(out, x, y, angle, speed, count, spread, kind="orb"):
    """`count` bullets spread evenly over `spread` radians around `angle`."""
    if count == 1:
        single(out, x, y, angle, speed, kind)
        return
    start = angle - spread / 2
    step = spread / (count - 1)
    for i in range(count):
        single(out, x, y, start + step * i, speed, kind)


def ring(out, x, y, count, speed, offset=0.0, kind="orb"):
    """`count` bullets in a full circle."""
    step = TAU / count
    for i in range(count):
        single(out, x, y, offset + step * i, speed, kind)
