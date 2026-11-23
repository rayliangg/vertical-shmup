"""把遊戲事件對應到音效，並播放背景音樂。"""
import pygame

from ..paths import SOUNDS_DIR

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
