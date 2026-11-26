"""遊戲規則：所有可以調整的數字都只寫在這裡。

這裡只放數字、字串、tuple 和 dict，因為 `scripts/export_web.py`
會把整個檔案轉成 `web/js/rules.js`，讓網頁版和 Python 版的規則完全一樣。
"""

# --- 場地 ----------------------------------------------------------------
WIDTH = 480
HEIGHT = 720
FPS = 60

# --- 玩家 ----------------------------------------------------------------
PLAYER_SPEED = 4.5
PLAYER_FOCUS_SPEED = 2.0            # 按住 Shift 的慢速精準移動
PLAYER_RADIUS = 5.0                 # 彈幕遊戲的超小判定點
PLAYER_GRAZE_RADIUS = 20.0          # 子彈擦過這個距離內就算擦彈
PLAYER_HALF_W = 25.0                # 機體圖片的一半大小，用來限制不能飛出畫面
PLAYER_HALF_H = 19.0
PLAYER_START_Y = 640.0
PLAYER_MAX_HP = 5
PLAYER_START_BOMBS = 2
PLAYER_MAX_BOMBS = 3
PLAYER_MAX_POWER = 4
INVULN_FRAMES = 90                  # 被打之後的無敵時間
SHIELD_INVULN_FRAMES = 60
BOMB_INVULN_FRAMES = 60
BOMB_DAMAGE = 12
AUTO_BOMB = True                    # 被打中時如果還有炸彈，就自動用炸彈抵銷
CONTACT_DAMAGE_TO_ENEMY = 5         # 撞到敵人時敵人也會受傷
DIAGONAL = 0.7071067811865476       # 1 / sqrt(2)，直接寫數字讓 JS 和 Python 算出來一樣

# --- 玩家武器 ------------------------------------------------------------
FIRE_INTERVAL = 6
SHOT_SPEED = 13.0
SHOT_RADIUS = 6.0
SHOT_DAMAGE = 1

# --- 道具 ----------------------------------------------------------------
ITEM_POWER = 0
ITEM_HEAL = 1
ITEM_SHIELD = 2
ITEM_BOMB = 3
ITEM_SCORE = 4
ITEM_NAMES = ("power", "heal", "shield", "bomb", "score")
ITEM_WEIGHTS = (30, 14, 10, 8, 38)
ITEM_SCORE_VALUE = 500
ITEM_RADIUS = 12.0
ITEM_PICKUP_RADIUS = 26.0
ITEM_FALL_SPEED = 1.6
ITEM_POP_SPEED = -2.2
ITEM_MAGNET_RADIUS = 70.0
ITEM_MAGNET_SPEED = 8.0
COLLECT_LINE_Y = 180.0              # 飛到這條線以上，所有道具都會自動吸過來

# --- 分數 ----------------------------------------------------------------
GRAZE_SCORE = 5
BULLET_CANCEL_SCORE = 10            # 炸彈或打倒魔王時，每消掉一顆子彈給的分數

# --- 敵人子彈 ------------------------------------------------------------
BULLET_RADIUS = {"orb": 5.0, "big": 9.0, "laser": 4.0}
BULLET_MARGIN = 24.0                # 飛出畫面這麼遠就刪掉

# --- 敵人 ----------------------------------------------------------------
# radius = 碰撞半徑，drop = 被打倒時掉道具的機率
ENEMIES = {
    "scout": {"hp": 3, "radius": 18.0, "score": 100, "drop": 0.12},
    "weaver": {"hp": 5, "radius": 20.0, "score": 150, "drop": 0.18},
    "diver": {"hp": 2, "radius": 18.0, "score": 120, "drop": 0.10},
    "gunship": {"hp": 22, "radius": 26.0, "score": 500, "drop": 1.0},
    "meteor_big": {"hp": 6, "radius": 30.0, "score": 50, "drop": 0.08},
    "meteor_medium": {"hp": 3, "radius": 15.0, "score": 30, "drop": 0.05},
    "meteor_small": {"hp": 1, "radius": 9.0, "score": 10, "drop": 0.0},
    # 魔王（"boss": True 會顯示血條，而且出現時雜魚會暫停）
    "boss_warden": {"hp": 360, "radius": 50.0, "score": 10000, "drop": 1.0, "boss": True},
    "boss_carrier": {"hp": 420, "radius": 46.0, "score": 12000, "drop": 1.0, "boss": True},
    "boss_fang": {"hp": 260, "radius": 44.0, "score": 9000, "drop": 1.0, "boss": True},
}
BOSS_HP_PER_STAGE = 0.30            # 第 2 關開始，每多一關魔王 HP +30%
BOSS_ITEM_DROPS = 8

# --- 魔王關卡 --------------------------------------------------------------
# 每一關：雜魚波次 -> WARNING -> 魔王（3 個階段）。一共 3 關：
#   第 1 關 Warden（1 隻）、第 2 關 Hive Carrier（1 隻）、第 3 關（最後一關）Twin Fang（2 隻）。
# 打倒最後一關的魔王就 ALL CLEAR，遊戲結束。
BOSS_ORDER = ("boss_warden", "boss_carrier", "boss_fang")
BOSS_NAMES = {
    "boss_warden": "WARDEN",
    "boss_carrier": "HIVE CARRIER",
    "boss_fang": "TWIN FANG",
}
# 每個階段的名稱會顯示在畫面上，類似彈幕遊戲的「符卡」。
PHASE_NAMES = {
    "boss_warden": ("Aimed Fans", "Twin Spiral", "Last Stand"),
    "boss_carrier": ("Drone Bay", "Bloom", "Laser Rain"),
    "boss_fang": ("Crossfire", "Pinwheel", "Fang Rush"),
}
PHASE_THRESHOLDS = (0.66, 0.33)     # HP 剩多少比例時進入第 2、第 3 階段
BOSS_PHASE_TIME = 1800              # 撐過 30 秒這個階段就時間到（沒有獎勵分）
PHASE_BONUS = 1000                  # 時間內打破一個階段的獎勵分
MAX_DRONES = 6                      # Hive Carrier 放出的無人機在畫面上最多幾隻
# 同時出場的魔王數量：Twin Fang 是兩台一起出現的雙魔王
BOSS_COUNT = {"boss_fang": 2}
TWIN_OFFSET = 110.0                 # 雙魔王離畫面中線的距離
RAGE_SPEEDUP = 2.0                  # 雙魔王其中一台被打倒後，另一台的射速倍率
FINAL_STAGE = 3                     # 最後一關
CLEAR_BONUS = 20000                 # ALL CLEAR 獎勵分
CLEAR_BONUS_PER_HP = 5000           # 通關時每剩 1 滴血再加的分數
ENEMY_CONTACT_SCALE = 0.8           # 敵人的碰撞範圍比圖片小一點

# --- Director（出怪控制） -----------------------------------------------
WAVE_INTERVAL_START = 150
WAVE_INTERVAL_MIN = 55
BOSS_TIME = 3600                    # 每關開始後第幾個 frame（60 秒）出現魔王警告
BOSS_WARNING_FRAMES = 150
DIFFICULTY_PER_STAGE = 0.25
DIFFICULTY_IN_STAGE = 0.35          # 魔王出現前難度會再往上加這麼多
# (波次名稱, 權重)，順序固定；Gunship 要過了 GUNSHIP_AFTER 個 frame 才會出現
WAVES = (
    ("scout_line", 3),
    ("scout_vee", 2),
    ("weavers", 3),
    ("divers", 2),
    ("meteors", 2),
    ("gunship", 1),
)
GUNSHIP_AFTER = 900
