"""pygame 前端：視窗、輸入、場景（標題 / 遊戲中 / 暫停 / 遊戲結束）。"""
import sys

import pygame

from ..agent.env import FRAME_SKIP
from ..agent.features import ACTIONS, observe
from ..core import World
from ..core import rules as R
from ..paths import HIGHSCORE_FILE, MODELS_DIR
from .assets import Assets
from .audio import Audio
from .renderer import Renderer, YELLOW

CONTROLS = (
    "ARROWS / WASD  move",
    "SHIFT  focus (slow)",
    "X  bomb",
    "TAB  autopilot on/off",
    "V  agent view    M  mute",
    "P  pause    ESC  quit",
)
TITLE, PLAYING, PAUSED, GAME_OVER = "title", "playing", "paused", "game_over"


def load_policy(path):
    """載入 DQN 自動駕駛；載入失敗就印出原因並回傳 None。"""
    if not path.exists():
        print("找不到模型 %s，請先用 scripts/train_cpu.py 訓練" % path, file=sys.stderr)
        return None
    try:
        from ..agent.policy import DQNPolicy
    except ImportError:
        print("自動駕駛需要 PyTorch：pip install torch", file=sys.stderr)
        return None
    return DQNPolicy.load(path)


class App:
    def __init__(self, autopilot=False, model_path=None, seed=None, speed=1):
        pygame.init()
        pygame.display.set_caption("Vertical Shmup")
        self.screen = pygame.display.set_mode((R.WIDTH, R.HEIGHT))
        self.clock = pygame.time.Clock()
        self.assets = Assets()
        self.audio = Audio(self.assets)
        self.renderer = Renderer(self.screen, self.assets)
        self.world = World(seed or 0)
        self.seed = seed
        self.model_path = model_path or (MODELS_DIR / "dqn.pt")
        self.policy = load_policy(self.model_path) if autopilot else None
        self.autopilot = self.policy is not None
        self.speed = max(1, int(speed))
        self.scene = PLAYING if self.autopilot else TITLE
        self.highscore = self._load_highscore()
        self.action = 0
        self.overlay = None
        self.over_timer = 0
        self.games = 0
        self.bomb_pressed = False

    # -- 最高分存檔 ---------------------------------------------------------
    @staticmethod
    def _load_highscore():
        try:
            return int(HIGHSCORE_FILE.read_text().strip())
        except (OSError, ValueError):
            return 0

    def _save_highscore(self):
        try:
            HIGHSCORE_FILE.write_text(str(self.highscore))
        except OSError:
            pass

    # -- 主迴圈 -------------------------------------------------------------
    def run(self):
        self.audio.play_music()
        if self.scene == PLAYING:
            self._new_game()
        running = True
        while running:
            self.clock.tick(R.FPS)
            running = self._handle_input()
            if self.scene == PLAYING:
                for _ in range(self.speed):
                    self._update()
                    if self.scene != PLAYING:
                        break
            self._draw()
            pygame.display.flip()
        pygame.quit()

    def _new_game(self):
        self.games += 1
        seed = self.seed if self.seed is not None else pygame.time.get_ticks() + self.games
        self.world.reset(seed)
        self.renderer.reset()
        self.scene = PLAYING

    def _toggle_autopilot(self):
        if self.policy is None:
            self.policy = load_policy(self.model_path)
        self.autopilot = self.policy is not None and not self.autopilot

    def _handle_input(self):
        bomb = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type != pygame.KEYDOWN:
                continue
            key = event.key
            if key == pygame.K_ESCAPE:
                return False
            if key == pygame.K_m:
                self.audio.toggle()
            elif key == pygame.K_v:
                self.renderer.show_agent_view = not self.renderer.show_agent_view
            elif key == pygame.K_TAB:
                self._toggle_autopilot()
            elif self.scene == TITLE and key in (pygame.K_RETURN, pygame.K_SPACE):
                self._new_game()
            elif self.scene == TITLE and key == pygame.K_a:
                self._toggle_autopilot()
                if self.autopilot:
                    self._new_game()
            elif self.scene == GAME_OVER and key in (pygame.K_RETURN, pygame.K_SPACE):
                self._new_game()
            elif self.scene in (PLAYING, PAUSED) and key == pygame.K_p:
                self.scene = PAUSED if self.scene == PLAYING else PLAYING
            elif self.scene == PLAYING and key == pygame.K_x:
                bomb = True
        self.bomb_pressed = bomb
        return True

    def _update(self):
        w = self.world
        if self.autopilot:
            if w.frame % FRAME_SKIP == 0:
                q = self.policy.q_values(w)
                self.action = int(q.argmax())
                if self.renderer.show_agent_view:
                    self.overlay = (self.policy.last_obs, q, self.action)
            dx, dy, focus = ACTIONS[self.action]
            bomb = False
        else:
            keys = pygame.key.get_pressed()
            dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
            dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
            focus = bool(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT])
            bomb = self.bomb_pressed
            self.bomb_pressed = False
            if self.renderer.show_agent_view and w.frame % FRAME_SKIP == 0:
                self.overlay = (observe(w), None, 0)
        w.step(dx, dy, focus, bomb)
        self.audio.handle(w.events)
        self.renderer.handle_events(w.events)
        if w.done:
            self.scene = GAME_OVER
            self.over_timer = 0
            if w.score > self.highscore:
                self.highscore = w.score
                self._save_highscore()

    # -- 畫面 -----------------------------------------------------------------
    def _draw(self):
        r = self.renderer
        if self.scene == TITLE:
            r.fx.starfield.update()
            r.fx.starfield.draw(self.screen, self.assets.image("backgrounds/dark_purple.png"))
            r.text("VERTICAL", 44, (R.WIDTH // 2, 150), YELLOW, "center")
            r.text("SHMUP", 44, (R.WIDTH // 2, 200), YELLOW, "center")
            r.text("ENTER  play", 18, (R.WIDTH // 2, 300), anchor="center")
            r.text("A  watch the DQN autopilot", 18, (R.WIDTH // 2, 332), anchor="center")
            for i, line in enumerate(CONTROLS):
                r.text(line, 12, (R.WIDTH // 2, 420 + i * 22), (180, 200, 255), "center", thin=True)
            r.text("HI %08d" % self.highscore, 14, (R.WIDTH // 2, R.HEIGHT - 50),
                   (255, 240, 150), "center")
            return
        r.draw(self.world, self.overlay)
        if self.autopilot:
            r.text("AUTOPILOT  (DQN)", 12, (R.WIDTH // 2, R.HEIGHT - 24), (80, 255, 120))
        if self.speed > 1:
            r.text("x%d" % self.speed, 12, (R.WIDTH - 8, R.HEIGHT - 24), anchor="topright")
        if self.scene == PAUSED:
            r.text("PAUSED", 34, (R.WIDTH // 2, R.HEIGHT // 2), anchor="center")
        elif self.scene == GAME_OVER:
            self.over_timer += 1
            r.text("GAME OVER", 38, (R.WIDTH // 2, R.HEIGHT // 2 - 40), (255, 90, 90), "center")
            r.text("SCORE %d" % self.world.score, 18, (R.WIDTH // 2, R.HEIGHT // 2 + 10),
                   anchor="center")
            r.text("HI %d" % self.highscore, 14, (R.WIDTH // 2, R.HEIGHT // 2 + 40),
                   (255, 240, 150), "center")
            r.text("ENTER  retry", 14, (R.WIDTH // 2, R.HEIGHT // 2 + 80), anchor="center")
            if self.autopilot and self.over_timer > 2 * R.FPS:
                self._new_game()
