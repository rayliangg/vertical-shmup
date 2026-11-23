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
    "boss": {"hp": 360, "radius": 50.0, "score": 10000, "drop": 1.0},
}
BOSS_HP_PER_STAGE = 0.35            # +35% boss HP each stage
BOSS_ITEM_DROPS = 8
ENEMY_CONTACT_SCALE = 0.8           # enemy bodies are a bit smaller than they look

# --- Director (wave spawning) --------------------------------------------
WAVE_INTERVAL_START = 150
WAVE_INTERVAL_MIN = 55
BOSS_TIME = 3600                    # frames into a stage before the boss warning
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
