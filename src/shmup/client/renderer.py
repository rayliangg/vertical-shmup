"""Draws a World with pygame: background, sprites, effects, HUD, agent overlay."""
import math

import pygame

from ..agent.features import ACTIONS, CELL, GRID, OFF_GRID
from ..core import rules as R
from .effects import Effects

BACKGROUNDS = ("dark_purple.png", "blue.png", "purple.png", "black.png")
ENEMY_SPRITES = {
    "scout": "enemies/scout.png", "weaver": "enemies/weaver.png",
    "diver": "enemies/diver.png", "gunship": "enemies/gunship.png",
    "midboss": "enemies/midboss.png", "boss_warden": "enemies/boss_warden.png",
    "boss_carrier": "enemies/boss_carrier.png", "boss_fang": "enemies/boss_fang.png",
    "meteor_big": "enemies/meteor_big.png",
    "meteor_medium": "enemies/meteor_medium.png", "meteor_small": "enemies/meteor_small.png",
}
ENEMY_WIDTH_SCALE = 2.7        # sprite width = radius * this
ITEM_SPRITES = ("items/power.png", "items/heal.png", "items/shield.png",
                "items/bomb.png", "items/score.png")
ITEM_COLORS = ((255, 210, 60), (90, 255, 120), (110, 200, 255), (255, 90, 90),
               (255, 240, 150))
ITEM_LABELS = ("POWER UP", "+1 HP", "SHIELD", "+1 BOMB", "+500")
BULLET_COLORS = {"orb": (255, 70, 130), "big": (180, 90, 255)}
WHITE = (255, 255, 255)
YELLOW = (255, 230, 90)


class Renderer:
    def __init__(self, screen, assets):
        self.screen = screen
        self.assets = assets
        self.world_surf = pygame.Surface((R.WIDTH, R.HEIGHT)).convert()
        self.fx = Effects()
        self.bank = 0.0
        self.tick = 0
        self.banner = None              # (text, frames_left, color)
        self.subtitle = None            # (boss phase name, frames_left)
        self.show_agent_view = False
        self._text_cache = {}

    # -- text ----------------------------------------------------------------
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

    # -- events -> effects ---------------------------------------------------
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
                if kind != "midboss":
                    self.subtitle = ("PHASE %d  %s" % (phase + 1, R.PHASE_NAMES[kind][phase].upper()),
                                     150)
            elif name == "boss_down":
                self.banner = ("STAGE %d" % value, 150, YELLOW)
                self.subtitle = None
            elif name == "escape":
                self.banner = ("BOSS ESCAPED", 120, (200, 200, 255))
                self.subtitle = None

    # -- frame -----------------------------------------------------------------
    def draw(self, world, overlay=None):
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
        if dx or dy:
            self.screen.fill((0, 0, 0))
        self.screen.blit(surf, (dx, dy))
        if self.fx.flash:
            veil = pygame.Surface((R.WIDTH, R.HEIGHT))
            veil.fill(WHITE)
            veil.set_alpha(int(18 * self.fx.flash))
            self.screen.blit(veil, (0, 0))
        if self.show_agent_view and overlay is not None:
            self._draw_agent_view(world, overlay)
        self._draw_hud(world)

    # -- entities ------------------------------------------------------------------
    def _draw_player(self, surf, p):
        self.bank += (p.move_x * -14 - self.bank) * 0.25
        angle = int(round(self.bank / 2.0)) * 2
        blink = p.invuln and (p.invuln // 4) % 2
        # engine flame
        flicker = 10 + (self.tick % 4) * 3
        cx, cy = int(p.x), int(p.y + R.PLAYER_HALF_H - 4)
        pygame.draw.polygon(surf, (255, 150, 40), [(cx - 6, cy), (cx + 6, cy), (cx, cy + flicker)])
        pygame.draw.polygon(surf, (255, 240, 160), [(cx - 3, cy), (cx + 3, cy), (cx, cy + flicker // 2)])
        if not blink:
            ship = self.assets.sprite("player/ship.png", int(R.PLAYER_HALF_W * 2), angle)
            surf.blit(ship, ship.get_rect(center=(int(p.x), int(p.y))))
        if p.shield:
            w = 74 + int(4 * math.sin(self.tick * 0.2))
            shield = self.assets.sprite("effects/shield.png", w)
            shield.set_alpha(170)
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

    # -- agent view (what the network sees) --------------------------------------------
    def _draw_agent_view(self, world, overlay):
        obs, q_values, action = overlay
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
        if q_values is not None:
            dx, dy, focus = ACTIONS[action]
            end = (int(p.x + dx * 40), int(p.y + dy * 40))
            pygame.draw.line(self.screen, (80, 255, 120), (int(p.x), int(p.y)), end, 3)
            self.text("Q %.2f%s" % (max(q_values), "  FOCUS" if focus else ""), 12,
                      (int(p.x), int(p.y) + 40), (80, 255, 120))

    def _draw_boss_bar(self, boss):
        scr, x, y, w = self.screen, 40, 80, R.WIDTH - 80
        self.text(R.BOSS_NAMES[boss.kind], 11, (x, y - 16), (255, 150, 150), "topleft")
        pygame.draw.rect(scr, (60, 20, 30), (x, y, w, 8))
        pygame.draw.rect(scr, (255, 70, 90), (x, y, int(w * boss.hp / boss.max_hp), 8))
        pygame.draw.rect(scr, WHITE, (x, y, w, 8), 1)
        if boss.kind != "midboss":
            for t in R.PHASE_THRESHOLDS:                   # phase dividers
                pygame.draw.line(scr, WHITE, (x + int(w * t), y - 2), (x + int(w * t), y + 9))
            left = max(0, R.BOSS_PHASE_TIME - boss.phase_timer) // R.FPS
            self.text("%02d" % left, 11, (x + w, y - 16), (255, 230, 150), "topright")

    # -- HUD ------------------------------------------------------------------
    def _draw_hud(self, world):
        p = world.player
        scr = self.screen
        self.text("%08d" % world.score, 20, (R.WIDTH // 2, 8))
        life = self.assets.sprite("ui/life.png", 22)
        for i in range(p.hp):
            scr.blit(life, (8 + i * 25, 8))
        bomb = self.assets.sprite("items/bomb.png", 18)
        for i in range(p.bombs):
            scr.blit(bomb, (8 + i * 22, 32))
        for i in range(R.PLAYER_MAX_POWER):
            color = (255, 210, 60) if i < p.power else (70, 70, 90)
            pygame.draw.rect(scr, color, (8 + i * 12, 56, 9, 5))
        self.text("STAGE %d" % world.stage, 12, (R.WIDTH - 8, 10), (180, 200, 255), "topright")
        self.text("GRAZE %d" % world.graze, 12, (R.WIDTH - 8, 28), (180, 200, 255), "topright",
                  thin=True)
        boss = world.boss
        if boss is not None and boss.state > 0:
            self._draw_boss_bar(boss)
        if self.subtitle:
            text, left = self.subtitle
            self.text(text, 14, (R.WIDTH // 2, 110), (255, 200, 120))
            self.subtitle = (text, left - 1) if left > 1 else None
        if self.banner:
            text, left, color = self.banner
            if (left // 12) % 2 == 0 or text != "WARNING":
                self.text(text, 34, (R.WIDTH // 2, R.HEIGHT // 3), color, "center")
            self.banner = (text, left - 1, color) if left > 1 else None
