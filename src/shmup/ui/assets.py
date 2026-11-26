"""圖片、字型、音效的載入與快取，以及「遊戲事件 -> 音效」（只有 pygame 版用）。"""
import math

import pygame

from ..paths import FONTS_DIR, IMAGES_DIR, SOUNDS_DIR


class Assets:
    def __init__(self):
        self._images = {}
        self._variants = {}
        self._fonts = {}
        self._sounds = {}

    # -- 圖片 --------------------------------------------------------------
    def image(self, name):
        """`name` 是 assets/images 底下的路徑，例如 'enemies/scout.png'。"""
        surf = self._images.get(name)
        if surf is None:
            surf = pygame.image.load(str(IMAGES_DIR / name)).convert_alpha()
            self._images[name] = surf
        return surf

    def sprite(self, name, width=None, angle=0, tint=None):
        """回傳縮放（維持比例）、旋轉或加亮過的複製，並快取起來。"""
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
        """用程式畫出來的圓形發光子彈。"""
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

    def band(self, width, height, color, alpha):
        """半透明的色帶（關卡標題、WARNING 用）。"""
        key = ("band", width, height, color, alpha)
        surf = self._variants.get(key)
        if surf is None:
            surf = pygame.Surface((width, height))
            surf.fill(color)
            surf.set_alpha(alpha)
            self._variants[key] = surf
        return surf

    def panel(self, width, height):
        """右邊資訊面板的底圖：暗色星空 + 金屬邊框，只畫一次。"""
        key = ("panel", width, height)
        surf = self._variants.get(key)
        if surf is None:
            surf = pygame.Surface((width, height)).convert()
            tile = self.image("backgrounds/black.png")
            for y in range(0, height, tile.get_height()):
                for x in range(0, width, tile.get_width()):
                    surf.blit(tile, (x, y))
            shade = pygame.Surface((width, height))
            shade.fill((10, 10, 30))
            shade.set_alpha(120)
            surf.blit(shade, (0, 0))
            pygame.draw.rect(surf, (20, 20, 28), (0, 0, 8, height))
            pygame.draw.line(surf, (150, 150, 170), (8, 0), (8, height), 2)
            pygame.draw.rect(surf, (90, 90, 110), (14, 90, width - 26, 270), 1)
            pygame.draw.rect(surf, (90, 90, 110), (14, 380, width - 26, 230), 1)
            self._variants[key] = surf
        return surf

    # -- 字型 --------------------------------------------------------------
    def font(self, size, thin=False):
        key = (size, thin)
        f = self._fonts.get(key)
        if f is None:
            name = "kenvector_future_thin.ttf" if thin else "kenvector_future.ttf"
            f = self._fonts[key] = pygame.font.Font(str(FONTS_DIR / name), size)
        return f

    # -- 音效 --------------------------------------------------------------
    def sound(self, name, volume=0.5):
        """`name` 是 assets/sounds/sfx 裡的檔名（不含副檔名）；沒有音效裝置就回傳 None。"""
        if not pygame.mixer.get_init():
            return None
        snd = self._sounds.get(name)
        if snd is None:
            snd = pygame.mixer.Sound(str(SOUNDS_DIR / "sfx" / (name + ".ogg")))
            snd.set_volume(volume)
            self._sounds[name] = snd
        return snd


# ---------------------------------------------------------------------------
# 音效：把遊戲事件對應到音效，並播放背景音樂
# ---------------------------------------------------------------------------
# 事件名稱 -> (音效檔, 音量)
EVENT_SOUNDS = {
    "explode": ("explosion", 0.35),
    "hurt": ("hurt", 0.6),
    "shield": ("shield_down", 0.6),
    "bomb": ("bomb", 0.7),
    "pickup": ("pickup", 0.35),
    "warning": ("warning", 0.7),
    "boss_down": ("stage_clear", 0.7),
    "gameover": ("game_over", 0.7),
}
SHOOT_EVERY = 3            # 每 3 次射擊才播一次雷射音效，不然太吵


class Audio:
    def __init__(self, assets):
        self.assets = assets
        self.enabled = True
        self._volleys = 0
        try:
            pygame.mixer.init()
        except pygame.error:
            self.enabled = False

    def play_music(self):
        if not self.enabled:
            return
        try:
            pygame.mixer.music.load(str(SOUNDS_DIR / "music" / "orbital_colossus.mp3"))
            pygame.mixer.music.set_volume(0.35)
            pygame.mixer.music.play(-1)
        except pygame.error:
            pass

    def toggle(self):
        self.enabled = not self.enabled
        if pygame.mixer.get_init():
            if self.enabled:
                pygame.mixer.music.unpause()
            else:
                pygame.mixer.music.pause()

    def handle(self, events):
        if not self.enabled or not pygame.mixer.get_init():
            return
        played = set()
        for name, _, _, value in events:
            if name == "shoot":
                self._volleys += 1
                if self._volleys % SHOOT_EVERY == 0:
                    self._play("shoot", 0.12)
            elif name == "pickup" and value == 2:
                self._play("shield_up", 0.5)
            elif name in EVENT_SOUNDS and name not in played:
                played.add(name)
                self._play(*EVENT_SOUNDS[name])

    def _play(self, name, volume):
        snd = self.assets.sound(name, volume)
        if snd is not None:
            snd.play()
