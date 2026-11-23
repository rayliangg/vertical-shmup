// Observation vector for the Q-network - exact port of src/shmup/agent/features.py.
(function (S) {
  "use strict";
  var R = S.RULES;

  var DIRS = [[0, 0], [-1, 0], [1, 0], [0, -1], [0, 1], [-1, -1], [1, -1], [-1, 1], [1, 1]];
  var ACTIONS = [];
  [false, true].forEach(function (focus) {
    DIRS.forEach(function (d) { ACTIONS.push([d[0], d[1], focus]); });
  });

  var N_BULLETS = 24, N_ENEMIES = 8, N_ITEMS = 2, GRID = 9, CELL = 28.0;
  var LOOKAHEAD = [[0, 1.0], [6, 0.75], [12, 0.5], [18, 0.25]];
  var POS_X = 240.0, POS_Y = 360.0, VEL = 6.0;
  var OFF_BULLETS = 7;
  var OFF_ENEMIES = OFF_BULLETS + N_BULLETS * 5;
  var OFF_GRID = OFF_ENEMIES + N_ENEMIES * 8;
  var OFF_ITEMS = OFF_GRID + GRID * GRID;
  var OFF_BOSS = OFF_ITEMS + N_ITEMS * 4;
  var OBS_DIM = OFF_BOSS + 4;

  function nearest(things, px, py, k) {
    var scored = [];
    for (var i = 0; i < things.length; i++) {
      var t = things[i];
      if (!t.alive) continue;
      var dx = t.x - px, dy = t.y - py;
      scored.push([dx * dx + dy * dy, i, t]);
    }
    scored.sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; });
    return scored.slice(0, k).map(function (s) { return s[2]; });
  }

  function mark(o, gx, gy, weight) {
    if (gx >= 0 && gx < GRID && gy >= 0 && gy < GRID) {
      var k = OFF_GRID + gy * GRID + gx;
      if (weight > o[k]) o[k] = weight;
    }
  }

  function dangerGrid(world, px, py, o) {
    var half = GRID / 2.0, i, j;
    for (i = 0; i < world.bullets.length; i++) {
      var b = world.bullets[i];
      if (!b.alive) continue;
      for (j = 0; j < LOOKAHEAD.length; j++) {
        var t = LOOKAHEAD[j][0];
        mark(o, Math.floor((b.x + b.vx * t - px) / CELL + half),
             Math.floor((b.y + b.vy * t - py) / CELL + half), LOOKAHEAD[j][1]);
      }
    }
    for (i = 0; i < world.enemies.length; i++) {
      var e = world.enemies[i];
      if (!e.alive) continue;
      var r = e.radius * R.ENEMY_CONTACT_SCALE;
      var x0 = Math.floor((e.x - r - px) / CELL + half);
      var x1 = Math.floor((e.x + r - px) / CELL + half);
      var y0 = Math.floor((e.y - r - py) / CELL + half);
      var y1 = Math.floor((e.y + r - py) / CELL + half);
      if (x1 < 0 || y1 < 0 || x0 >= GRID || y0 >= GRID) continue;
      for (var gy = Math.max(y0, 0); gy <= Math.min(y1, GRID - 1); gy++) {
        for (var gx = Math.max(x0, 0); gx <= Math.min(x1, GRID - 1); gx++) mark(o, gx, gy, 1.0);
      }
    }
  }

  // Returns a Float64Array(OBS_DIM) (or fills `out`).
  function observe(world, out) {
    var o = out || new Float64Array(OBS_DIM);
    if (out) o.fill(0);
    var p = world.player, px = p.x, py = p.y, j, list, i;

    o[0] = px / R.WIDTH * 2 - 1;
    o[1] = py / R.HEIGHT * 2 - 1;
    o[2] = p.hp / R.PLAYER_MAX_HP;
    o[3] = p.bombs / R.PLAYER_MAX_BOMBS;
    o[4] = (p.power - 1) / (R.PLAYER_MAX_POWER - 1);
    o[5] = p.shield ? 1.0 : 0.0;
    o[6] = p.invuln / R.INVULN_FRAMES;

    j = OFF_BULLETS;
    list = nearest(world.bullets, px, py, N_BULLETS);
    for (i = 0; i < list.length; i++, j += 5) {
      var b = list[i];
      o[j] = (b.x - px) / POS_X;
      o[j + 1] = (b.y - py) / POS_Y;
      o[j + 2] = b.vx / VEL;
      o[j + 3] = b.vy / VEL;
      o[j + 4] = b.r / 10.0;
    }

    j = OFF_ENEMIES;
    list = nearest(world.enemies, px, py, N_ENEMIES);
    for (i = 0; i < list.length; i++, j += 8) {
      var e = list[i];
      o[j] = (e.x - px) / POS_X;
      o[j + 1] = (e.y - py) / POS_Y;
      o[j + 2] = e.vx / VEL;
      o[j + 3] = e.vy / VEL;
      o[j + 4] = e.radius / 50.0;
      o[j + 5] = e.hp / e.maxHp;
      o[j + 6] = e.isBoss ? 1.0 : 0.0;
      o[j + 7] = 1.0;
    }

    dangerGrid(world, px, py, o);

    j = OFF_ITEMS;
    list = nearest(world.items, px, py, N_ITEMS);
    for (i = 0; i < list.length; i++, j += 4) {
      var it = list[i];
      o[j] = (it.x - px) / POS_X;
      o[j + 1] = (it.y - py) / POS_Y;
      o[j + 2] = it.kind / 4.0;
      o[j + 3] = 1.0;
    }

    var boss = world.boss();
    if (boss !== null) {
      o[OFF_BOSS] = 1.0;
      o[OFF_BOSS + 1] = (boss.x - px) / POS_X;
      o[OFF_BOSS + 2] = (boss.y - py) / POS_Y;
      o[OFF_BOSS + 3] = boss.hp / boss.maxHp;
    }
    return o;
  }

  S.Features = {
    ACTIONS: ACTIONS, OBS_DIM: OBS_DIM, GRID: GRID, CELL: CELL, OFF_GRID: OFF_GRID,
    observe: observe
  };
})(this.Shmup = this.Shmup || {});
