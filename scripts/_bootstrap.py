"""讓腳本不用先 `pip install -e .` 也能 `import shmup`（把 ../src 加進 sys.path）。"""
import os
import sys

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)
