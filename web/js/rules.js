// 由 scripts/export_web.py 自動產生，請不要手動修改。
(function (S) {
  S.RULES = {
    "AUTO_BOMB": true,
    "BOMB_DAMAGE": 12,
    "BOMB_INVULN_FRAMES": 60,
    "BOSS_COUNT": {
      "boss_fang": 2
    },
    "BOSS_HP_PER_STAGE": 0.3,
    "BOSS_ITEM_DROPS": 8,
    "BOSS_NAMES": {
      "boss_carrier": "HIVE CARRIER",
      "boss_fang": "TWIN FANG",
      "boss_warden": "WARDEN"
    },
    "BOSS_ORDER": [
      "boss_warden",
      "boss_carrier",
      "boss_fang"
    ],
    "BOSS_PHASE_TIME": 1800,
    "BOSS_TIME": 3600,
    "BOSS_WARNING_FRAMES": 150,
    "BULLET_CANCEL_SCORE": 10,
    "BULLET_MARGIN": 24.0,
    "BULLET_RADIUS": {
      "big": 9.0,
      "laser": 4.0,
      "orb": 5.0
    },
    "CLEAR_BONUS": 20000,
    "CLEAR_BONUS_PER_HP": 5000,
    "COLLECT_LINE_Y": 180.0,
    "CONTACT_DAMAGE_TO_ENEMY": 5,
    "DIAGONAL": 0.7071067811865476,
    "DIFFICULTY_IN_STAGE": 0.35,
    "DIFFICULTY_PER_STAGE": 0.25,
    "ENEMIES": {
      "boss_carrier": {
        "boss": true,
        "drop": 1.0,
        "hp": 420,
        "radius": 46.0,
        "score": 12000
      },
      "boss_fang": {
        "boss": true,
        "drop": 1.0,
        "hp": 260,
        "radius": 44.0,
        "score": 9000
      },
      "boss_warden": {
        "boss": true,
        "drop": 1.0,
        "hp": 360,
        "radius": 50.0,
        "score": 10000
      },
      "diver": {
        "drop": 0.1,
        "hp": 2,
        "radius": 18.0,
        "score": 120
      },
      "gunship": {
        "drop": 1.0,
        "hp": 22,
        "radius": 26.0,
        "score": 500
      },
      "meteor_big": {
        "drop": 0.08,
        "hp": 6,
        "radius": 30.0,
        "score": 50
      },
      "meteor_medium": {
        "drop": 0.05,
        "hp": 3,
        "radius": 15.0,
        "score": 30
      },
      "meteor_small": {
        "drop": 0.0,
        "hp": 1,
        "radius": 9.0,
        "score": 10
      },
      "scout": {
        "drop": 0.12,
        "hp": 3,
        "radius": 18.0,
        "score": 100
      },
      "weaver": {
        "drop": 0.18,
        "hp": 5,
        "radius": 20.0,
        "score": 150
      }
    },
    "ENEMY_CONTACT_SCALE": 0.8,
    "FINAL_STAGE": 3,
    "FIRE_INTERVAL": 6,
    "FPS": 60,
    "GRAZE_SCORE": 5,
    "GUNSHIP_AFTER": 900,
    "HEIGHT": 720,
    "INVULN_FRAMES": 90,
    "ITEM_BOMB": 3,
    "ITEM_FALL_SPEED": 1.6,
    "ITEM_HEAL": 1,
    "ITEM_MAGNET_RADIUS": 70.0,
    "ITEM_MAGNET_SPEED": 8.0,
    "ITEM_NAMES": [
      "power",
      "heal",
      "shield",
      "bomb",
      "score"
    ],
    "ITEM_PICKUP_RADIUS": 26.0,
    "ITEM_POP_SPEED": -2.2,
    "ITEM_POWER": 0,
    "ITEM_RADIUS": 12.0,
    "ITEM_SCORE": 4,
    "ITEM_SCORE_VALUE": 500,
    "ITEM_SHIELD": 2,
    "ITEM_WEIGHTS": [
      30,
      14,
      10,
      8,
      38
    ],
    "MAX_DRONES": 6,
    "PHASE_BONUS": 1000,
    "PHASE_NAMES": {
      "boss_carrier": [
        "Drone Bay",
        "Bloom",
        "Laser Rain"
      ],
      "boss_fang": [
        "Crossfire",
        "Pinwheel",
        "Fang Rush"
      ],
      "boss_warden": [
        "Aimed Fans",
        "Twin Spiral",
        "Last Stand"
      ]
    },
    "PHASE_THRESHOLDS": [
      0.66,
      0.33
    ],
    "PLAYER_FOCUS_SPEED": 2.0,
    "PLAYER_GRAZE_RADIUS": 20.0,
    "PLAYER_HALF_H": 19.0,
    "PLAYER_HALF_W": 25.0,
    "PLAYER_MAX_BOMBS": 3,
    "PLAYER_MAX_HP": 5,
    "PLAYER_MAX_POWER": 4,
    "PLAYER_RADIUS": 5.0,
    "PLAYER_SPEED": 4.5,
    "PLAYER_START_BOMBS": 2,
    "PLAYER_START_Y": 640.0,
    "RAGE_SPEEDUP": 2.0,
    "SHIELD_INVULN_FRAMES": 60,
    "SHOT_DAMAGE": 1,
    "SHOT_RADIUS": 6.0,
    "SHOT_SPEED": 13.0,
    "TWIN_OFFSET": 110.0,
    "WAVES": [
      [
        "scout_line",
        3
      ],
      [
        "scout_vee",
        2
      ],
      [
        "weavers",
        3
      ],
      [
        "divers",
        2
      ],
      [
        "meteors",
        2
      ],
      [
        "gunship",
        1
      ]
    ],
    "WAVE_INTERVAL_MIN": 55,
    "WAVE_INTERVAL_START": 150,
    "WIDTH": 480
  };
})(this.Shmup = this.Shmup || {});
