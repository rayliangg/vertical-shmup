"""Command-line entry point.

    python -m shmup                    # play
    python -m shmup --autopilot        # watch the trained DQN play
    python -m shmup --autopilot --speed 3
"""
import argparse
from pathlib import Path


def main(argv=None):
    ap = argparse.ArgumentParser(prog="shmup", description="Vertical bullet-hell shooter")
    ap.add_argument("--autopilot", action="store_true", help="let the DQN agent fly")
    ap.add_argument("--model", type=Path, default=None, help="checkpoint (default models/dqn.pt)")
    ap.add_argument("--seed", type=int, default=None, help="fixed seed for every game")
    ap.add_argument("--speed", type=int, default=1, help="simulation steps per frame")
    args = ap.parse_args(argv)

    from .client.app import App          # import pygame only when actually playing
    App(args.autopilot, args.model, args.seed, args.speed).run()


if __name__ == "__main__":
    main()
