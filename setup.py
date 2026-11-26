# -*- coding: utf-8 -*-
"""安裝設定。版本固定在 requirements.txt（全部 2022-05-27 以前）；這裡只寫範圍。

    pip install -e .        # 安裝這個專案（之後就能用 python -m shmup …）
"""
from setuptools import find_packages, setup

setup(
    name="vertical-shmup",
    version="3.0.0",
    description="縱向彈幕射擊遊戲 + Stable Baselines3 PPO 自動駕駛",
    package_dir={"": "src"},
    packages=find_packages("src"),
    python_requires=">=3.8,<3.11",
    install_requires=[
        "stable-baselines3==1.5.0",
        "gym==0.21.0",
        "torch>=1.8.1,<=1.11.0",
        "numpy>=1.20,<=1.22.4",
        "pygame>=2.0,<=2.1.2",
        "matplotlib<=3.5.2",
        "pandas<=1.4.2",
    ],
    entry_points={"console_scripts": ["shmup = shmup.__main__:main"]},
)
