# -*- coding: utf-8 -*-
"""安裝設定。

    pip install -e .                # 只裝遊戲模擬需要的 numpy
    pip install -e ".[game]"        # 加上 pygame，才能開視窗玩
    pip install -e ".[game,rl]"     # 再加上 Stable Baselines3（含 PyTorch、gymnasium），才能訓練 / 自動駕駛
"""
from setuptools import find_packages, setup

setup(
    name="vertical-shmup",
    version="3.0.0",
    description="縱向彈幕射擊遊戲 + Stable Baselines3 PPO 自動駕駛",
    package_dir={"": "src"},
    packages=find_packages("src"),
    python_requires=">=3.9",
    install_requires=["numpy>=1.20"],
    extras_require={
        "game": ["pygame>=2.0"],
        "rl": ["stable-baselines3>=2.0", "gymnasium>=0.28"],
        "dev": ["pytest>=6.0"],
    },
    entry_points={"console_scripts": ["shmup = shmup.__main__:main"]},
)
