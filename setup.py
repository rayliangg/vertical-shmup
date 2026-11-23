# -*- coding: utf-8 -*-
"""安裝設定（用傳統的 setup.py，2019 年以前的 pip / setuptools 都能用）。

    pip install -e .                # 只裝模擬需要的 numpy
    pip install -e ".[game]"        # 加上 pygame，才能開視窗玩
    pip install -e ".[game,rl]"     # 再加上 PyTorch，才能訓練 / 自動駕駛
"""
from setuptools import find_packages, setup

setup(
    name="vertical-shmup",
    version="2.0.0",
    description="縱向彈幕射擊遊戲 + DQN 自動駕駛",
    package_dir={"": "src"},
    packages=find_packages("src"),
    python_requires=">=3.6",
    install_requires=["numpy>=1.15"],
    extras_require={
        "game": ["pygame>=1.9.4"],
        "rl": ["torch>=1.0"],
        "dev": ["pytest>=4.0"],
    },
    entry_points={"console_scripts": ["shmup = shmup.__main__:main"]},
)
