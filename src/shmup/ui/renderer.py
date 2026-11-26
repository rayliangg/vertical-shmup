"""用 pygame 畫出 World：背景、角色、特效、HUD、agent 視角。"""
import math

import pygame

from ..rl.features import ACTIONS, CELL, GRID, OFF_GRID
from ..game import rules as R
from .effects import Effects, faded

BACKGROUNDS = ("dark_purple.png", "blue.png", "purple.png", "black.png")
ENEMY_SPRITES = {
    "scout": "enemies/scout.png", "weaver": "enemies/weaver.png",
    "diver": "enemies/diver.png", "gunship": "enemies/gunship.png",
    "boss_warden": "enemies/boss_warden.png",
    "boss_fang": "enemies/boss_fang.png",
    "meteor_big": "enemies/meteor_big.png",
    "meteor_medium": "enemies/meteor_medium.png", "meteor_small": "enemies/meteor_small.png",
}
ENEMY_WIDTH_SCALE = 2.7        # 圖片寬度 = 碰撞半徑 * 這個倍數
ITEM_SPRITES = ("items/power.png", "items/heal.png", "items/shield.png",
                "items/bomb.png", "items/score.png")
ITEM_COLORS = ((255, 210, 60), (90, 255, 120), (110, 200, 255), (255, 90, 90),
               (255, 240, 150))
ITEM_LABELS = ("POWER UP", "+1 HP", "SHIELD", "+1 BOMB", "+500")
BULLET_COLORS = {"orb": (255, 70, 130), "big": (180, 90, 255)}
WHITE = (255, 255, 255)
YELLOW = (255, 230, 90)
PANEL_W = 280                  # 右邊資訊面板的寬度
SCREEN_W = R.WIDTH + PANEL_W   # 整個視窗寬度


class Renderer:
    def __init__(self, screen, assets):
        self.screen = screen
        self.assets = assets
        self.world_surf = pygame.Surface((R.WIDTH, R.HEIGHT)).convert()
        self.fx = Effects()
        self.bank = 0.0
        self.tick = 0
        self.banner = None              # (文字, 剩幾個 frame, 顏色)
        self.subtitle = None            # (魔王階段名稱, 剩幾個 frame)
        self.show_agent_view = False
        self._text_cache = {}

    # -- 文字 ----------------------------------------------------------------
    def text_surface(self, text, size, color=WHITE, thin=False):
        key = (text, size, color, thin)
        surf = self._text_cache.get(key)
        if surf is None:
            if len(self._text_cache) > 400:
                self._text_cache.clear()
            surf = self.assets.font(size, thin).render(text, True, color)
            self._text_cache[key] = surf
        return surf

    def text(self, text, size, pos, color=WHITE, anchor="midtop", thin=False, target=None):
        target = target or self.screen
        shadow = self.text_surface(text, size, (0, 0, 0), thin)
        surf = self.text_surface(text, size, color, thin)
        rect = surf.get_rect(**{anchor: pos})
        target.blit(shadow, rect.move(2, 2))
        target.blit(surf, rect)

    # -- 遊戲事件 -> 特效 ---------------------------------------------------
    def reset(self):
        self.fx.clear()
        self.subtitle = None
        self.banner = ("STAGE 1", 120, YELLOW)

    def handle_events(self, events):
        fx = self.fx
        for name, x, y, value in events:
            if name == "explode":
                is_boss = R.ENEMIES[value].get("boss", False)
                fx.explosion(x, y, big=is_boss)
                if value in ("gunship", "meteor_big"):
                    fx.shake = max(fx.shake, 5.0)
            elif name == "hit":
                fx.sparks(x, y, (255, 255, 200), 3, 3.0, 10, 2)
            elif name == "hurt":
                fx.shake = max(fx.shake, 12.0)
                fx.sparks(x, y, (255, 80, 80), 20, 6.0, 30, 3)
                fx.ring(x, y, (255, 80, 80), 6.0, 20, 4)
            elif name == "shield":
                fx.ring(x, y, (120, 200, 255), 8.0, 22, 5)
            elif name == "bomb":
                fx.ring(x, y, (255, 255, 255), 14.0, 40, 8)
                fx.ring(x, y, (255, 120, 120), 10.0, 45, 4)
                fx.flash = 8
                fx.shake = max(fx.shake, 8.0)
                self.banner = ("AUTO BOMB" if value else "BOMB", 50, (255, 120, 120))
            elif name == "cancel":
                fx.sparks(x, y, (255, 240, 150), 2, 1.5, 20, 2)
            elif name == "graze":
                fx.sparks(x, y, (200, 220, 255), 2, 2.0, 8, 2)
            elif name == "pickup":
                fx.sparks(x, y, ITEM_COLORS[value], 10, 3.0, 20, 2)
                fx.popup(self.text_surface(ITEM_LABELS[value], 12, ITEM_COLORS[value]), x, y - 16)
            elif name == "warning":
                self.banner = ("WARNING", R.BOSS_WARNING_FRAMES, (255, 60, 60))
            elif name == "boss":
                self.banner = (R.BOSS_NAMES[value], 100, (255, 120, 120))
            elif name == "phase":
                kind, phase = value
                self.subtitle = ("PHASE %d  %s" % (phase + 1, R.PHASE_NAMES[kind][phase].upper()), 150)
            elif name == "boss_down":
                self.banner = ("STAGE %d" % value, 150, YELLOW)
                self.subtitle = None
            elif name == "clear":
                self.banner = ("ALL CLEAR" if value else "BOSS ESCAPED", 600, YELLOW)
                self.subtitle = None
            elif name == "rage":
                self.banner = ("RAGE MODE", 90, (255, 80, 80))
            elif name == "escape":
                self.banner = ("BOSS ESCAPED", 120, (200, 200, 255))
                self.subtitle = None

    # -- 每一個 frame -------------------------------------------------------
    def draw(self, world, overlay=None, hud=None):
        """畫一整個畫面。hud 是給右邊面板的資訊：hiscore、autopilot、action、label。"""
        self.tick += 1
        surf = self.world_surf
        bg = self.assets.image("backgrounds/" + BACKGROUNDS[(world.stage - 1) % len(BACKGROUNDS)])
        boost = 3.0 if world.director.state == 1 else 1.0
        self.fx.starfield.update(boost)
        self.fx.starfield.draw(surf, bg)

        self._draw_items(surf, world)
        self._draw_shots(surf, world)
        self._draw_enemies(surf, world)
        self._draw_player(surf, world.player)
        self._draw_bullets(surf, world)
        self.fx.update()
        self.fx.draw(surf)

        dx, dy = self.fx.offset()
        play = pygame.Rect(0, 0, R.WIDTH, R.HEIGHT)
        self.screen.set_clip(play)                   # 畫面震動時不要蓋到右邊面板
        if dx or dy:
            self.screen.fill((0, 0, 0), play)
        self.screen.blit(surf, (dx, dy))
        if self.fx.flash:
            veil = pygame.Surface((R.WIDTH, R.HEIGHT))
            veil.fill(WHITE)
            veil.set_alpha(int(18 * self.fx.flash))
            self.screen.blit(veil, (0, 0))
        if self.show_agent_view and overlay is not None:
            self._draw_agent_view(world, overlay)
        self._draw_playfield_hud(world)
        self.screen.set_clip(None)
        self.draw_panel(world, hud or {})

    # -- 遊戲物件 ------------------------------------------------------------------
    def _draw_player(self, surf, p):
        self.bank += (p.move_x * -14 - self.bank) * 0.25
        angle = int(round(self.bank / 2.0)) * 2
        blink = p.invuln and (p.invuln // 4) % 2
        # 引擎火焰
        flicker = 10 + (self.tick % 4) * 3
        cx, cy = int(p.x), int(p.y + R.PLAYER_HALF_H - 4)
        pygame.draw.polygon(surf, (255, 150, 40), [(cx - 6, cy), (cx + 6, cy), (cx, cy + flicker)])
        pygame.draw.polygon(surf, (255, 240, 160), [(cx - 3, cy), (cx + 3, cy), (cx, cy + flicker // 2)])
        if not blink:
            ship = self.assets.sprite("player/ship.png", int(R.PLAYER_HALF_W * 2), angle)
            surf.blit(ship, ship.get_rect(center=(int(p.x), int(p.y))))
        if p.shield:
            w = 74 + int(4 * math.sin(self.tick * 0.2))
            shield = faded(self.assets.sprite("effects/shield.png", w), 170)
            surf.blit(shield, shield.get_rect(center=(int(p.x), int(p.y) - 4)))
        if p.focus or self.show_agent_view:
            pygame.draw.circle(surf, (255, 60, 60), (int(p.x), int(p.y)), int(R.PLAYER_RADIUS) + 2)
            pygame.draw.circle(surf, WHITE, (int(p.x), int(p.y)), int(R.PLAYER_RADIUS))

    def _draw_enemies(self, surf, world):
        for e in world.enemies:
            width = int(e.radius * ENEMY_WIDTH_SCALE)
            angle = 0
            if e.kind.startswith("meteor"):
                angle = int((e.age * 3 + e.home_x) % 360) // 6 * 6
            tint = (110, 110, 110) if e.flash else None
            img = self.assets.sprite(ENEMY_SPRITES[e.kind], width, angle, tint)
            x, y = e.x, e.y
            if e.kind == "diver" and e.state == 1:
                x += self.fx.rng.uniform(-2, 2)
            surf.blit(img, img.get_rect(center=(int(x), int(y))))

    def _draw_bullets(self, surf, world):
        for b in world.bullets:
            if b.kind == "laser":
                angle = int(round(-math.degrees(math.atan2(b.vy, b.vx)) - 90) / 10) * 10
                img = self.assets.sprite("projectiles/enemy_laser.png", 9, angle % 360)
            else:
                img = self.assets.glow(int(b.r), BULLET_COLORS[b.kind])
            surf.blit(img, img.get_rect(center=(int(b.x), int(b.y))))

    def _draw_shots(self, surf, world):
        name = ("projectiles/player_laser_max.png" if world.player.power >= R.PLAYER_MAX_POWER
                else "projectiles/player_laser.png")
        for s in world.shots:
            angle = int(round(-math.degrees(math.atan2(s.vx, -s.vy)) / 5.0)) * 5
            img = self.assets.sprite(name, 8, angle)
            surf.blit(img, img.get_rect(center=(int(s.x), int(s.y))))

    def _draw_items(self, surf, world):
        for it in world.items:
            bob = 3 * math.sin((it.age + it.x) * 0.12)
            pygame.draw.circle(surf, ITEM_COLORS[it.kind], (int(it.x), int(it.y + bob)),
                               int(R.ITEM_RADIUS + 3 + 2 * math.sin(self.tick * 0.2)), 1)
            img = self.assets.sprite(ITEM_SPRITES[it.kind], 24)
            surf.blit(img, img.get_rect(center=(int(it.x), int(it.y + bob))))

    # -- agent 視角（網路看到的東西） --------------------------------------------
    def _draw_agent_view(self, world, overlay):
        obs, probs, action = overlay
        p = world.player
        layer = pygame.Surface((R.WIDTH, R.HEIGHT), pygame.SRCALPHA)
        x0 = p.x - CELL * GRID / 2.0
        y0 = p.y - CELL * GRID / 2.0
        for gy in range(GRID):
            for gx in range(GRID):
                v = obs[OFF_GRID + gy * GRID + gx]
                rect = (int(x0 + gx * CELL), int(y0 + gy * CELL), int(CELL) - 1, int(CELL) - 1)
                if v > 0:
                    pygame.draw.rect(layer, (255, 40, 40, int(40 + 120 * v)), rect)
                else:
                    pygame.draw.rect(layer, (80, 200, 255, 40), rect, 1)
        self.screen.blit(layer, (0, 0))
        if probs is not None:
            dx, dy, focus = ACTIONS[action]
            end = (int(p.x + dx * 40), int(p.y + dy * 40))
            pygame.draw.line(self.screen, (80, 255, 120), (int(p.x), int(p.y)), end, 3)
            self.text("%d%%%s" % (round(100 * max(probs)), "  FOCUS" if focus else ""), 12,
                      (int(p.x), int(p.y) + 40), (80, 255, 120))

    # -- 遊戲區裡的 HUD：魔王血條、階段名稱、ENEMY 標記、標題帶 -------------------
    def _draw_playfield_hud(self, world):
        scr = self.screen
        bosses = [e for e in world.enemies if e.is_boss and e.alive and e.state > 0]
        for i, boss in enumerate(bosses[:2]):
            self._draw_boss_bar(boss, 22 + i * 20)
            # 彈幕遊戲常見的 ENEMY 標記：在畫面底邊標出魔王的 x 位置
            mx = int(min(max(boss.x, 14), R.WIDTH - 14))
            pygame.draw.polygon(scr, (255, 70, 90), [(mx - 7, R.HEIGHT), (mx + 7, R.HEIGHT),
                                                    (mx, R.HEIGHT - 9)])
            self.text("ENEMY", 9, (mx, R.HEIGHT - 22), (255, 120, 130), "midtop", thin=True)
        if self.subtitle:
            text, left = self.subtitle
            y = 26 + 20 * min(len(bosses), 2)
            self.text(text, 13, (R.WIDTH - 10, y), (255, 200, 120), "topright")
            self.subtitle = (text, left - 1) if left > 1 else None
        if self.banner:
            text, left, color = self.banner
            band = self.assets.band(R.WIDTH, 64, (0, 0, 0), 150)
            if text == "WARNING":
                band = self.assets.band(R.WIDTH, 64, (120, 0, 0), 150)
            y = R.HEIGHT // 3
            if (left // 12) % 2 == 0 or text != "WARNING":
                scr.blit(band, (0, y - 32))
                pygame.draw.line(scr, color, (0, y - 32), (R.WIDTH, y - 32), 2)
                pygame.draw.line(scr, color, (0, y + 31), (R.WIDTH, y + 31), 2)
                self.text(text, 30, (R.WIDTH // 2, y), color, "center")
            self.banner = (text, left - 1, color) if left > 1 else None

    def _draw_boss_bar(self, boss, y):
        scr, x, w = self.screen, 10, R.WIDTH - 60
        self.text(R.BOSS_NAMES[boss.kind], 10, (x, y - 13), (255, 150, 150), "topleft")
        if boss.rage:
            self.text("RAGE", 10, (x + w, y - 13), (255, 80, 80), "topright")
        pygame.draw.rect(scr, (60, 20, 30), (x, y, w, 6))
        pygame.draw.rect(scr, (255, 70, 90), (x, y, int(w * max(boss.hp, 0) / boss.max_hp), 6))
        pygame.draw.rect(scr, WHITE, (x, y, w, 6), 1)
        for t in R.PHASE_THRESHOLDS:                       # 階段分隔線
            pygame.draw.line(scr, WHITE, (x + int(w * t), y - 2), (x + int(w * t), y + 7))
        left = max(0, R.BOSS_PHASE_TIME - boss.phase_timer) // R.FPS
        self.text("%02d" % left, 14, (R.WIDTH - 8, y - 6), (255, 230, 150), "topright")

    # -- 右邊的資訊面板（彈幕遊戲常見的版面） ---------------------------------
    def draw_panel(self, world, hud):
        scr, x0 = self.screen, R.WIDTH
        scr.blit(self.assets.panel(PANEL_W, R.HEIGHT), (x0, 0))
        lx, rx = x0 + 22, x0 + PANEL_W - 22
        self.text("VERTICAL", 22, (x0 + PANEL_W // 2, 24), YELLOW)
        self.text("SHMUP", 22, (x0 + PANEL_W // 2, 50), YELLOW)

        def row(y, label, value=None, color=WHITE):
            self.text(label, 13, (lx, y), (170, 190, 255), "topleft")
            if value is not None:
                self.text(value, 15, (rx, y - 1), color, "topright")

        p = world.player
        row(110, "HI-SCORE", "%09d" % max(hud.get("hiscore", 0), world.score), (255, 240, 150))
        row(140, "SCORE", "%09d" % world.score)
        row(190, "PLAYER")
        life = self.assets.sprite("ui/life.png", 20)
        empty = faded(life, 60)
        for i in range(R.PLAYER_MAX_HP):
            scr.blit(life if i < p.hp else empty, (lx + 92 + i * 24, 190))
        row(220, "BOMB")
        bomb = self.assets.sprite("items/bomb.png", 18)
        for i in range(R.PLAYER_MAX_BOMBS):
            scr.blit(bomb if i < p.bombs else faded(bomb, 60), (lx + 92 + i * 24, 219))
        row(250, "POWER", "MAX" if p.power >= R.PLAYER_MAX_POWER else None, (255, 210, 60))
        for i in range(R.PLAYER_MAX_POWER):
            color = (255, 210, 60) if i < p.power else (60, 60, 80)
            pygame.draw.rect(scr, color, (lx + 92 + i * 22, 255, 18, 8))
        row(280, "GRAZE", str(world.graze))
        row(310, "STAGE", str(world.stage))
        if p.shield:
            self.text("SHIELD ON", 12, (lx, 340), (120, 200, 255), "topleft")

        if hud.get("autopilot"):
            self.text("AUTOPILOT", 15, (x0 + PANEL_W // 2, 400), (80, 255, 120))
            self._draw_joystick(x0 + PANEL_W // 2, 470, hud.get("action"))
        if hud.get("label"):
            self.text(hud["label"], 15, (x0 + PANEL_W // 2, 560), (255, 200, 120))
        if hud.get("sublabel"):
            self.text(hud["sublabel"], 11, (x0 + PANEL_W // 2, 584), (180, 180, 200), thin=True)
        self.text("PPO AUTOPILOT DEMO", 10, (x0 + PANEL_W // 2, R.HEIGHT - 30),
                  (110, 110, 140), thin=True)

    def _draw_joystick(self, cx, cy, action):
        """3x3 搖桿燈號：亮起來的那格是 AI 選的方向，SLOW 燈表示慢速。"""
        scr = self.screen
        lit, slow = None, False
        if action is not None:
            dx, dy, slow = ACTIONS[action]
            lit = (dx, dy)
        for gy in (-1, 0, 1):
            for gx in (-1, 0, 1):
                rect = (cx - 45 + (gx + 1) * 30 - 12, cy + gy * 30 - 12, 26, 26)
                on = lit == (gx, gy)
                pygame.draw.rect(scr, (60, 220, 85) if on else (40, 40, 50), rect)
                pygame.draw.rect(scr, (180, 255, 190) if on else (80, 80, 95), rect, 2)
        lamp = (cx + 60, cy - 12, 52, 24)
        pygame.draw.rect(scr, (255, 150, 40) if slow else (40, 40, 50), lamp)
        pygame.draw.rect(scr, (90, 90, 100), lamp, 2)
        self.text("SLOW", 11, (cx + 86, cy), (0, 0, 0) if slow else (110, 110, 120), "center")
