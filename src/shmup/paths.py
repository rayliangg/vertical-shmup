"""所有檔案路徑，都是相對於專案根目錄。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS_DIR = ROOT / "assets"
IMAGES_DIR = ASSETS_DIR / "images"
SOUNDS_DIR = ASSETS_DIR / "sounds"
FONTS_DIR = ASSETS_DIR / "fonts"
MODELS_DIR = ROOT / "models"
WEB_DIR = ROOT / "web"
HIGHSCORE_FILE = ROOT / ".highscore"
