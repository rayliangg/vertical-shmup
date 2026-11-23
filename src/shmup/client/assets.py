"""Image, font and sound loading with caching (pygame only)."""
import math

import pygame

from ..paths import FONTS_DIR, IMAGES_DIR, SOUNDS_DIR


class Assets:
    def __init__(self):
        self._images = {}
        self._variants = {}
        self._fonts = {}
        self._sounds = {}

    # -- images ------------------------------------------------------------
    def image(self, name):
        """`name` is a path below assets/images, e.g. 'enemies/scout.png'."""
        surf = self._images.get(name)
        if surf is None:
            surf = pygame.image.load(str(IMAGES_DIR / name)).convert_alpha()
            self._images[name] = surf
        return surf

    def sprite(self, name, width=None, angle=0, tint=None):
        """Scaled (keeping aspect), rotated and/or tinted copy, cached."""
        key = (name, width, angle, tint)
        surf = self._variants.get(key)
        if surf is None:
            surf = self.image(name)
            if width is not None and width != surf.get_width():
                h = max(1, int(round(surf.get_height() * width / float(surf.get_width()))))
                surf = pygame.transform.smoothscale(surf, (int(width), h))
            if tint is not None:
                surf = surf.copy()
                surf.fill(tint + (0,), special_flags=pygame.BLEND_RGBA_ADD)
            if angle:
                surf = pygame.transform.rotate(surf, angle)
            self._variants[key] = surf
        return surf

    def glow(self, radius, color, core=True):
        """Soft round bullet sprite drawn procedurally."""
        key = ("glow", radius, color, core)
        surf = self._variants.get(key)
        if surf is None:
            size = int(radius * 4)
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            c = size / 2.0
            for i in range(8, 0, -1):
                r = radius * (1 + i * 0.12)
                a = int(40 * (1 - i / 9.0))
                pygame.draw.circle(surf, color + (a,), (int(c), int(c)), int(math.ceil(r)))
            pygame.draw.circle(surf, color + (255,), (int(c), int(c)), int(radius))
            if core:
                pygame.draw.circle(surf, (255, 255, 255, 255), (int(c), int(c)),
                                   max(1, int(radius * 0.55)))
            self._variants[key] = surf
        return surf

    # -- fonts -------------------------------------------------------------
    def font(self, size, thin=False):
        key = (size, thin)
        f = self._fonts.get(key)
        if f is None:
            name = "kenvector_future_thin.ttf" if thin else "kenvector_future.ttf"
            f = self._fonts[key] = pygame.font.Font(str(FONTS_DIR / name), size)
        return f

    # -- sounds ------------------------------------------------------------
    def sound(self, name, volume=0.5):
        """`name` is a file in assets/sounds/sfx without extension. None if no audio."""
        if not pygame.mixer.get_init():
            return None
        snd = self._sounds.get(name)
        if snd is None:
            snd = pygame.mixer.Sound(str(SOUNDS_DIR / "sfx" / (name + ".ogg")))
            snd.set_volume(volume)
            self._sounds[name] = snd
        return snd
