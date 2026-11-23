"""Gameplay rules: the single source of truth for every tunable number.

Only plain numbers, strings, tuples and dicts live here, because
`scripts/export_web.py` copies this module into `web/js/rules.js` so the
browser version plays by exactly the same rules as the Python one.
"""

# --- Arena ---------------------------------------------------------------
WIDTH = 480
HEIGHT = 720
FPS = 60

# --- Player --------------------------------------------------------------
PLAYER_SPEED = 4.5
PLAYER_FOCUS_SPEED = 2.0            # slow, precise movement (hold Shift)
PLAYER_RADIUS = 5.0                 # tiny bullet-hell hit box
PLAYER_GRAZE_RADIUS = 20.0          # bullets passing this close score a graze
PLAYER_HALF_W = 25.0                # sprite half size, used to clamp movement
PLAYER_HALF_H = 19.0
PLAYER_START_Y = 640.0
PLAYER_MAX_HP = 5
PLAYER_START_BOMBS = 2
PLAYER_MAX_BOMBS = 3
PLAYER_MAX_POWER = 4
INVULN_FRAMES = 90                  # mercy frames after a hit
SHIELD_INVULN_FRAMES = 60
BOMB_INVULN_FRAMES = 60
BOMB_DAMAGE = 12
AUTO_BOMB = True                    # a hit spends a bomb instead of HP if one is left
CONTACT_DAMAGE_TO_ENEMY = 5         # ramming an enemy hurts it too
DIAGONAL = 0.7071067811865476       # 1 / sqrt(2), written out so JS and Python agree

# --- Player weapon -------------------------------------------------------
FIRE_INTERVAL = 6
SHOT_SPEED = 13.0
SHOT_RADIUS = 6.0
SHOT_DAMAGE = 1

# --- Items ---------------------------------------------------------------
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
COLLECT_LINE_Y = 180.0              # fly above this line and every item comes to you

# --- Scoring -------------------------------------------------------------
GRAZE_SCORE = 5
BULLET_CANCEL_SCORE = 10            # per enemy bullet erased by a bomb / boss kill

# --- Enemy bullets -------------------------------------------------------
BULLET_RADIUS = {"orb": 5.0, "big": 9.0, "laser": 4.0}
BULLET_MARGIN = 24.0                # removed once this far outside the arena

# --- Enemies -------------------------------------------------------------
# radius = hit circle, drop = chance to drop an item when destroyed
ENEMIES = {
    "scout": {"hp": 3, "radius": 18.0, "score": 100, "drop": 0.12},
    "weaver": {"hp": 5, "radius": 20.0, "score": 150, "drop": 0.18},
    "diver": {"hp": 2, "radius": 18.0, "score": 120, "drop": 0.10},
    "gunship": {"hp": 22, "radius": 26.0, "score": 500, "drop": 1.0},
    "meteor_big": {"hp": 6, "radius": 30.0, "score": 50, "drop": 0.08},
    "meteor_medium": {"hp": 3, "radius": 15.0, "score": 30, "drop": 0.05},
    "meteor_small": {"hp": 1, "radius": 9.0, "score": 10, "drop": 0.0},
    # bosses ("boss": True shows the HP bar and pauses the waves)
    "midboss": {"hp": 120, "radius": 32.0, "score": 3000, "drop": 1.0, "boss": True},
    "boss_warden": {"hp": 360, "radius": 50.0, "score": 10000, "drop": 1.0, "boss": True},
    "boss_carrier": {"hp": 420, "radius": 46.0, "score": 12000, "drop": 1.0, "boss": True},
    "boss_fang": {"hp": 400, "radius": 44.0, "score": 15000, "drop": 1.0, "boss": True},
}
BOSS_HP_PER_STAGE = 0.30            # +30% boss HP for every stage after the first
BOSS_ITEM_DROPS = 8
MIDBOSS_ITEM_DROPS = 3

# --- Boss stages -----------------------------------------------------------
# Each stage: waves -> mid-boss -> waves -> WARNING -> stage boss (3 phases).
# The stage boss cycles Warden -> Carrier -> Fang -> Warden (harder) -> ...
BOSS_ORDER = ("boss_warden", "boss_carrier", "boss_fang")
BOSS_NAMES = {
    "midboss": "SENTINEL",
    "boss_warden": "WARDEN",
    "boss_carrier": "HIVE CARRIER",
    "boss_fang": "TWIN FANG",
}
# Phase names shown as a banner, like "spell cards" in danmaku games.
PHASE_NAMES = {
    "midboss": ("Ring Guard", "Ring Guard", "Ring Guard"),
    "boss_warden": ("Aimed Fans", "Twin Spiral", "Last Stand"),
    "boss_carrier": ("Drone Bay", "Bloom", "Laser Rain"),
    "boss_fang": ("Crossfire", "Pinwheel", "Fang Rush"),
}
PHASE_THRESHOLDS = (0.66, 0.33)     # HP fraction where phase 2 and phase 3 start
BOSS_PHASE_TIME = 1800              # survive 30 s and the phase times out (no bonus)
PHASE_BONUS = 1000                  # score for breaking a phase before the timeout
MIDBOSS_TIME = 1500                 # frames into a stage when the mid-boss appears
MIDBOSS_ESCAPE = 1500               # mid-boss leaves after this many frames
MAX_DRONES = 6                      # Hive Carrier's launched divers on screen
ENEMY_CONTACT_SCALE = 0.8           # enemy bodies are a bit smaller than they look

# --- Director (wave spawning) --------------------------------------------
WAVE_INTERVAL_START = 150
WAVE_INTERVAL_MIN = 55
BOSS_TIME = 4200                    # frames into a stage before the boss warning
BOSS_WARNING_FRAMES = 150
DIFFICULTY_PER_STAGE = 0.25
DIFFICULTY_IN_STAGE = 0.35          # extra difficulty reached right before the boss
# (wave name, weight), in a fixed order; gunships only after GUNSHIP_AFTER frames
WAVES = (
    ("scout_line", 3),
    ("scout_vee", 2),
    ("weavers", 3),
    ("divers", 2),
    ("meteors", 2),
    ("gunship", 1),
)
GUNSHIP_AFTER = 900
