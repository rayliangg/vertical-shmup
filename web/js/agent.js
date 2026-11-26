// 網頁版的 AI：觀測向量（對照 src/shmup/rl/features.py）+ PPO 策略網路推論。

// Q 網路的觀測向量：完全對照 src/shmup/rl/features.py。
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

  // 回傳 Float64Array(OBS_DIM)（或直接填進 `out`）。
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

// 用純 JavaScript 算 PPO 的策略網路（不需要任何機器學習函式庫）。
// 權重來自 web/model/ppo_model.js，由 python -m shmup export 從 Stable Baselines3 的模型匯出。
// 網路：284 個觀測 -> Linear+tanh -> Linear+tanh -> Linear -> 18 個動作的 logits。
(function (S) {
  "use strict";

  function decode(b64) {
    var bin = atob(b64), bytes = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new Float32Array(bytes.buffer);          // little-endian 的 float32
  }

  function Linear(spec) {
    this.nIn = spec["in"];
    this.nOut = spec.out;
    this.w = decode(spec.w);                         // [輸出][輸入]，row-major 排列
    this.b = decode(spec.b);
    this.act = spec.act;                             // "tanh"、"relu" 或 "none"
  }
  Linear.prototype.forward = function (x) {
    var y = new Float32Array(this.nOut), w = this.w, n = this.nIn;
    for (var o = 0; o < this.nOut; o++) {
      var s = this.b[o], base = o * n;
      for (var i = 0; i < n; i++) s += w[base + i] * x[i];
      if (this.act === "tanh") s = Math.tanh(s);
      else if (this.act === "relu" && s < 0) s = 0;
      y[o] = s;
    }
    return y;
  };

  function Policy(model) {
    this.layers = model.layers.map(function (l) { return new Linear(l); });
    this.meta = model.meta || {};
    this.obsDim = model.obs_dim;
  }

  Policy.prototype.logits = function (obs) {
    var x = obs;
    for (var i = 0; i < this.layers.length; i++) x = this.layers[i].forward(x);
    return x;
  };

  // 回傳 { action: 機率最高的動作, probs: 18 個動作的機率 }
  Policy.prototype.act = function (obs) {
    var z = this.logits(obs), best = 0, i, max = -Infinity, sum = 0;
    for (i = 0; i < z.length; i++) if (z[i] > max) { max = z[i]; best = i; }
    var probs = new Float32Array(z.length);
    for (i = 0; i < z.length; i++) { probs[i] = Math.exp(z[i] - max); sum += probs[i]; }
    for (i = 0; i < z.length; i++) probs[i] /= sum;
    return { action: best, probs: probs };
  };

  S.Policy = Policy;
  S.loadPolicy = function () {
    if (!S.MODEL) return null;
    if (S.MODEL.obs_dim !== S.Features.OBS_DIM) {
      console.warn("模型需要", S.MODEL.obs_dim, "維輸入，但遊戲提供", S.Features.OBS_DIM,
                   "維，請重新匯出模型。");
      return null;
    }
    return new Policy(S.MODEL);
  };
})(this.Shmup = this.Shmup || {});
