"""錄影：把訓練中存下來的模型拿來玩一局並錄成 mp4（不用開視窗）。

    python -m shmup record                                  # 錄 10 / 50 / 500 / 2000 回合的模型
    python -m shmup record --episodes 10 2000 --seconds 60

每個模型都用同一個 seed 玩，所以可以直接比較「練越久是不是越會躲」。
需要電腦裡有 ffmpeg（只用來把畫面壓成 mp4）。輸出在 videos/。
"""
import os
import shutil
import subprocess
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")      # 不開視窗
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

from ..game import World  # noqa: E402
from ..game import rules as R  # noqa: E402
from ..rl.env import FRAME_SKIP  # noqa: E402
from ..rl.features import ACTIONS  # noqa: E402
from ..rl.policy import PPOPolicy  # noqa: E402

FPS = R.FPS


def open_ffmpeg(path, width, height):
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (width, height),
           "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "22", "-preset", "veryfast",
           str(path)]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def record(checkpoint, episode, out_path, seed, seconds, screen, renderer):
    policy = PPOPolicy.load(checkpoint)
    world = World(seed)
    renderer.reset()
    width, height = screen.get_size()
    ff = open_ffmpeg(out_path, width, height)
    to_bytes = getattr(pygame.image, "tobytes", None) or pygame.image.tostring

    action, hold = 0, 0
    label = "EPISODE %d" % episode
    sub = "step %s" % "{:,}".format(int(policy.model.num_timesteps))
    for frame in range(int(seconds * FPS)):
        if not world.done:
            if world.frame % FRAME_SKIP == 0:
                action = policy(world)
            dx, dy, focus = ACTIONS[action]
            world.step(dx, dy, focus)
            renderer.handle_events(world.events)
        renderer.draw(world, None, {"hiscore": 0, "autopilot": True,
                                    "action": None if world.done else action,
                                    "label": label, "sublabel": sub})
        if world.done:
            title = "ALL CLEAR!" if world.cleared else ("THE END" if world.player.hp > 0 else "GAME OVER")
            renderer.text(title, 38, (R.WIDTH // 2, R.HEIGHT // 2 - 30), (255, 90, 90), "center")
            renderer.text("SCORE %d" % world.score, 18, (R.WIDTH // 2, R.HEIGHT // 2 + 20),
                          anchor="center")
            hold += 1
            if hold > 2 * FPS:                      # 死掉之後再停 2 秒就結束
                break
        ff.stdin.write(to_bytes(screen, "RGB"))
    ff.stdin.close()
    ff.wait()
    survived = world.frame / float(FPS)
    print("  第 %4d 回合的權重：活了 %.1f 秒，分數 %d，打到第 %d 關%s -> %s"
          % (episode, survived, world.score, world.stage,
             "（ALL CLEAR）" if world.cleared else "", out_path))
    return survived


def make_grid(paths, out_path, width, height):
    """把 4 支影片排成 2x2，長度不同的會停在最後一格畫面。"""
    w, h = width // 2, height // 2
    inputs = []
    for p in paths:
        inputs += ["-i", str(p)]
    pads = "".join("[%d:v]scale=%d:%d,tpad=stop_mode=clone:stop=-1[v%d];" % (i, w, h, i)
                   for i in range(len(paths)))
    layout = "0_0|%d_0|0_%d|%d_%d" % (w, h, w, h)
    filt = pads + "".join("[v%d]" % i for i in range(len(paths))) + \
        "xstack=inputs=%d:layout=%s:shortest=0[out]" % (len(paths), layout)
    longest = max(float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]))
        for p in paths)
    cmd = ["ffmpeg", "-y", "-loglevel", "error"] + inputs + [
        "-filter_complex", filt, "-map", "[out]", "-t", "%.2f" % longest,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23", "-preset", "veryfast",
        str(out_path)]
    subprocess.check_call(cmd)
    print("  2x2 對照影片 -> %s" % out_path)


def record_all(checkpoint_dir, episodes, out_dir, seed=100000, seconds=120, grid=True):
    """錄每個里程碑模型各一支影片；4 支都有的話再合成 2x2 對照影片。"""
    if shutil.which("ffmpeg") is None:
        sys.exit("找不到 ffmpeg，請先安裝（macOS：brew install ffmpeg；Colab 已內建）")
    os.makedirs(out_dir, exist_ok=True)
    pygame.init()
    from .assets import Assets
    from .renderer import SCREEN_W, Renderer
    screen = pygame.display.set_mode((SCREEN_W, R.HEIGHT))
    renderer = Renderer(screen, Assets())
    done = []
    for ep in episodes:
        ckpt = os.path.join(str(checkpoint_dir), "ppo_ep%d.zip" % ep)
        if not os.path.exists(ckpt):
            print("  找不到 %s，跳過" % ckpt)
            continue
        out = os.path.join(str(out_dir), "episode_%04d.mp4" % ep)
        record(ckpt, ep, out, seed, seconds, screen, renderer)
        done.append(out)
    if grid and len(done) == 4:
        make_grid(done, os.path.join(str(out_dir), "compare_2x2.mp4"), SCREEN_W, R.HEIGHT)
