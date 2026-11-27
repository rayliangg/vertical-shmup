// 網頁版的遊戲模擬：亂數（xorshift32）+ 整個遊戲規則。對照 src/shmup/game/。

// xorshift32 亂數：完全對照 src/shmup/game/rng.py（同一個 seed 會產生同樣的亂數）。
(function (S) {
  "use strict";

  function Rng(seed) {
    this.seed(seed === undefined ? 1 : seed);
  }

  Rng.prototype.seed = function (seed) {
    var s = (Math.imul(seed >>> 0, 2654435761 | 0) + 0x9E3779B9) >>> 0;
    this.state = s || 0x6D2B79F5;
  };

  Rng.prototype.nextU32 = function () {
    var x = this.state;
    x = (x ^ (x << 13)) >>> 0;
    x = (x ^ (x >>> 17)) >>> 0;
    x = (x ^ (x << 5)) >>> 0;
    this.state = x;
    return x;
  };

  Rng.prototype.random = function () { return this.nextU32() / 4294967296; };
  Rng.prototype.uniform = function (a, b) { return a + (b - a) * this.random(); };
  Rng.prototype.randint = function (a, b) { return a + Math.floor(this.random() * (b - a + 1)); };
  Rng.prototype.chance = function (p) { return this.random() < p; };

  // pairs：[[key, 權重], ...]
  Rng.prototype.weighted = function (pairs) {
    var total = 0, i;
    for (i = 0; i < pairs.length; i++) total += pairs[i][1];
    var r = this.random() * total;
    for (i = 0; i < pairs.length; i++) {
      r -= pairs[i][1];
      if (r < 0) return pairs[i][0];
    }
    return pairs[pairs.length - 1][0];
  };

  S.Rng = Rng;
})(this.Shmup = this.Shmup || {});

// 遊戲模擬：逐行對照 src/shmup/game 移植過來的（world、entities、
// enemies、patterns、director）。兩邊要一起改：tests/test_web_parity.py
// 會用同一個 seed 分別跑 Python 和 Node，比較結果是否一樣。
(function (S) {
  "use strict";
  var R = S.RULES;
  var HALF_PI = Math.PI / 2;
  var TAU = 2 * Math.PI;
  var ITEM_CHOICES = R.ITEM_WEIGHTS.map(function (w, i) { return [i, w]; });

  // ---------------------------------------------------------------- 玩家、子彈、道具
  function Player() {
    this.x = R.WIDTH / 2;
    this.y = R.PLAYER_START_Y;
    this.hp = R.PLAYER_MAX_HP;
    this.bombs = R.PLAYER_START_BOMBS;
    this.power = 1;
    this.shield = false;
    this.invuln = 0;
    this.fireCooldown = 0;
    this.moveX = 0;
    this.focus = false;
  }

  Player.prototype.move = function (dx, dy, focus) {
    var speed = focus ? R.PLAYER_FOCUS_SPEED : R.PLAYER_SPEED;
    if (dx && dy) speed *= R.DIAGONAL;
    this.x = Math.min(Math.max(this.x + dx * speed, R.PLAYER_HALF_W), R.WIDTH - R.PLAYER_HALF_W);
    this.y = Math.min(Math.max(this.y + dy * speed, R.PLAYER_HALF_H), R.HEIGHT - R.PLAYER_HALF_H);
    this.moveX = dx;
    this.focus = focus;
  };

  Player.prototype.shots = function () {
    var x = this.x, y = this.y - R.PLAYER_HALF_H, s = R.SHOT_SPEED, p = this.power;
    if (p === 1) return [new Shot(x, y, 0, -s)];
    if (p === 2) return [new Shot(x - 8, y, 0, -s), new Shot(x + 8, y, 0, -s)];
    if (p === 3) return [new Shot(x, y, 0, -s), new Shot(x - 6, y, -1.6, -s), new Shot(x + 6, y, 1.6, -s)];
    return [new Shot(x - 8, y, 0, -s), new Shot(x + 8, y, 0, -s),
            new Shot(x - 10, y, -2.6, -s), new Shot(x + 10, y, 2.6, -s),
            new Shot(x, y - 6, 0, -s)];
  };

  function Shot(x, y, vx, vy) {
    this.x = x; this.y = y; this.vx = vx; this.vy = vy; this.alive = true;
  }
  Shot.prototype.update = function () {
    this.x += this.vx;
    this.y += this.vy;
    if (this.y < -20 || this.x < -20 || this.x > R.WIDTH + 20) this.alive = false;
  };

  function Bullet(x, y, vx, vy, kind) {
    this.x = x; this.y = y; this.vx = vx; this.vy = vy;
    this.kind = kind || "orb";
    this.r = R.BULLET_RADIUS[this.kind];
    this.grazed = false;
    this.alive = true;
  }
  Bullet.prototype.update = function () {
    this.x += this.vx;
    this.y += this.vy;
    var m = R.BULLET_MARGIN;
    if (this.x < -m || this.x > R.WIDTH + m || this.y < -m || this.y > R.HEIGHT + m) this.alive = false;
  };

  function Item(x, y, kind) {
    this.x = x; this.y = y; this.kind = kind;
    this.vy = R.ITEM_POP_SPEED;
    this.magnet = false;
    this.alive = true;
    this.age = 0;
  }
  Item.prototype.update = function (player) {
    this.age += 1;
    var dx = player.x - this.x, dy = player.y - this.y;
    var d2 = dx * dx + dy * dy;
    if (!this.magnet && (player.y < R.COLLECT_LINE_Y ||
                         d2 < R.ITEM_MAGNET_RADIUS * R.ITEM_MAGNET_RADIUS)) {
      this.magnet = true;
    }
    if (this.magnet) {
      var d = Math.sqrt(d2);
      if (d > 1e-6) {
        var step = Math.min(R.ITEM_MAGNET_SPEED, d);
        this.x += dx / d * step;
        this.y += dy / d * step;
      }
    } else {
      this.vy = Math.min(this.vy + 0.08, R.ITEM_FALL_SPEED);
      this.y += this.vy;
      if (this.y > R.HEIGHT + 20) this.alive = false;
    }
  };

  // ---------------------------------------------------------------- 發射方式
  function aimAngle(x, y, t) { return Math.atan2(t.y - y, t.x - x); }
  function single(out, x, y, angle, speed, kind) {
    out.push(new Bullet(x, y, Math.cos(angle) * speed, Math.sin(angle) * speed, kind));
  }
  function fan(out, x, y, angle, speed, count, spread, kind) {
    if (count === 1) { single(out, x, y, angle, speed, kind); return; }
    var start = angle - spread / 2, step = spread / (count - 1);
    for (var i = 0; i < count; i++) single(out, x, y, start + step * i, speed, kind);
  }
  function ring(out, x, y, count, speed, offset, kind) {
    var step = TAU / count;
    for (var i = 0; i < count; i++) single(out, x, y, (offset || 0) + step * i, speed, kind);
  }

  // ---------------------------------------------------------------- 敵人
  function Enemy(kind, x, y, vx, vy, hp) {
    var spec = R.ENEMIES[kind];
    this.kind = kind;
    this.x = x; this.y = y; this.vx = vx || 0; this.vy = vy || 0;
    this.hp = this.maxHp = (hp === undefined ? spec.hp : hp);
    this.radius = spec.radius;
    this.score = spec.score;
    this.drop = spec.drop;
    this.age = 0;
    this.alive = true;
    this.state = 0;
    this.timer = 0;
    this.fireTimer = 60;
    this.altTimer = 60;
    this.homeX = x;
    this.amp = 0;
    this.phase = 0;
    this.targetY = 0;
    this.flash = 0;
    this.isBoss = spec.boss === true;
    this.phaseIndex = 0;
    this.phaseTimer = 0;
    this.rage = false;
  }
  Enemy.prototype.damageable = function () { return this.y > 10; };
  Enemy.prototype.update = function (w) {
    this.age += 1;
    if (this.flash) this.flash -= 1;
    UPDATERS[this.kind](this, w);
  };

  function interval(base, d) { return Math.max(4, Math.floor(base / d)); }
  function offscreen(e, margin) {
    margin = margin === undefined ? 60 : margin;
    return e.y > R.HEIGHT + margin || e.y < -margin - 40 || e.x < -margin || e.x > R.WIDTH + margin;
  }

  function scout(e, w) {
    e.x += e.vx;
    e.y += e.vy;
    if (e.y > 0) {
      e.fireTimer -= 1;
      if (e.fireTimer <= 0) {
        single(w.bullets, e.x, e.y, aimAngle(e.x, e.y, w.player), 3.0 * w.bulletSpeed());
        e.fireTimer = interval(90, w.difficulty());
      }
    }
    if (e.y > R.HEIGHT + 40) e.alive = false;
  }

  function weaver(e, w) {
    var nx = e.homeX + e.amp * Math.sin(e.age * 0.03 + e.phase);
    e.vx = nx - e.x;
    e.x = nx;
    e.y += e.vy;
    if (e.y > 0) {
      e.fireTimer -= 1;
      if (e.fireTimer <= 0) {
        fan(w.bullets, e.x, e.y, HALF_PI, 2.6 * w.bulletSpeed(), 3, 0.5);
        e.fireTimer = interval(110, w.difficulty());
      }
    }
    if (e.y > R.HEIGHT + 40) e.alive = false;
  }

  function diver(e, w) {
    if (e.state === 0) {
      e.y += e.vy;
      if (e.y >= e.targetY) { e.state = 1; e.timer = 35; e.vy = 0; }
    } else if (e.state === 1) {
      e.timer -= 1;
      if (e.timer <= 0) {
        var a = aimAngle(e.x, e.y, w.player), speed = 7.5 * w.bulletSpeed();
        e.vx = Math.cos(a) * speed;
        e.vy = Math.sin(a) * speed;
        e.state = 2;
      }
    } else {
      e.x += e.vx;
      e.y += e.vy;
      if (offscreen(e)) e.alive = false;
    }
  }

  function gunship(e, w) {
    if (e.state === 0) {
      e.y += e.vy;
      if (e.y >= e.targetY) { e.state = 1; e.timer = 300; e.vy = 0; }
    } else if (e.state === 1) {
      e.vx = Math.sin(e.age * 0.02) * 0.8;
      e.x += e.vx;
      e.fireTimer -= 1;
      if (e.fireTimer <= 0) {
        var count = 10 + 2 * Math.min(w.stage - 1, 4);
        ring(w.bullets, e.x, e.y, count, 2.2 * w.bulletSpeed(), e.age * 0.05);
        e.fireTimer = interval(80, w.difficulty());
      }
      e.altTimer -= 1;
      if (e.altTimer <= 0) {
        single(w.bullets, e.x, e.y, aimAngle(e.x, e.y, w.player), 5.5 * w.bulletSpeed(), "laser");
        e.altTimer = interval(55, w.difficulty());
      }
      e.timer -= 1;
      if (e.timer <= 0) { e.state = 2; e.vx = 0; e.vy = -1.2; }
    } else {
      e.y += e.vy;
      if (e.y < -60) e.alive = false;
    }
  }

  function meteor(e) {
    e.x += e.vx;
    e.y += e.vy;
    if (offscreen(e)) e.alive = false;
  }

  // ---------------------------------------------------------------- 魔王
  var ENTRY_Y = { boss_warden: 130.0, boss_fang: 120.0 };

  function sway(e, center, amp, speed) {
    e.phase += speed;
    var nx = center + amp * Math.sin(e.phase);
    e.vx = nx - e.x;
    e.x = nx;
  }

  function bossPhases(e, w) {
    if (e.state === 0) {
      e.y += 1.5;
      if (e.y >= e.targetY) {
        e.state = 1;
        w.emit("boss", e.x, e.y, e.kind);
        w.emit("phase", e.x, e.y, [e.kind, 0]);
      }
      return false;
    }
    e.phaseTimer += 1;
    var frac = e.hp / e.maxHp, T = R.PHASE_THRESHOLDS;
    var phase = frac > T[0] ? 0 : (frac > T[1] ? 1 : 2);
    if (phase !== e.phaseIndex) {
      w.bossPhaseChange(e, phase, false);
    } else if (e.phaseTimer >= R.BOSS_PHASE_TIME) {
      if (e.phaseIndex < 2) {
        e.hp = Math.floor(e.maxHp * T[e.phaseIndex]);
        w.bossPhaseChange(e, e.phaseIndex + 1, true);
      } else {
        w.bossEscaped(e);
        return false;
      }
    }
    e.fireTimer -= 1;
    e.altTimer -= 1;
    return true;
  }

  function warden(e, w) {
    if (!bossPhases(e, w)) return;
    sway(e, R.WIDTH / 2, 140, 0.012);
    var bs = w.bulletSpeed(), d = w.difficulty(), a;
    if (e.phaseIndex === 0) {
      if (e.fireTimer <= 0) {
        a = aimAngle(e.x, e.y, w.player);
        fan(w.bullets, e.x, e.y + 30, a, 3.4 * bs, 5, 0.6);
        e.fireTimer = interval(50, d);
      }
      if (e.altTimer <= 0) {
        ring(w.bullets, e.x, e.y, 20, 1.9 * bs, e.amp, "big");
        e.amp += 0.3;
        e.altTimer = interval(130, d);
      }
    } else if (e.phaseIndex === 1) {
      if (e.fireTimer <= 0) {
        single(w.bullets, e.x, e.y, e.amp, 2.5 * bs);
        single(w.bullets, e.x, e.y, e.amp + Math.PI, 2.5 * bs);
        e.amp += 0.22;
        e.fireTimer = 5;
      }
      if (e.altTimer <= 0) {
        a = aimAngle(e.x, e.y, w.player);
        fan(w.bullets, e.x, e.y + 30, a, 6.0 * bs, 3, 0.25, "laser");
        e.altTimer = interval(90, d);
      }
    } else {
      if (e.fireTimer <= 0) {
        ring(w.bullets, e.x, e.y, 24, 2.4 * bs, e.amp);
        e.amp += 0.13;
        e.fireTimer = interval(30, d);
      }
      if (e.altTimer <= 0) {
        a = aimAngle(e.x, e.y, w.player);
        single(w.bullets, e.x, e.y + 30, a, 4.2 * bs);
        e.altTimer = 10;
      }
    }
  }

  function fang(e, w) {
    if (!bossPhases(e, w)) return;
    var bs = w.bulletSpeed() * R.FANG_BULLET_SCALE, d = w.difficulty() * R.FANG_FIRE_SCALE, a, k;
    if (e.rage) d = d * R.RAGE_SPEEDUP;
    var side = e.homeX < R.WIDTH / 2 ? -1.0 : 1.0;
    if (e.phaseIndex < 2) {
      sway(e, e.homeX, 80, 0.02);
    } else {
      e.vx = Math.min(Math.max(w.player.x + side * 60 - e.x, -3.0), 3.0);
      e.x += e.vx;
    }
    if (e.phaseIndex === 0) {
      if (e.fireTimer <= 0) {
        for (var side = -1; side <= 1; side += 2) {
          var gx = e.x + side * 50, gy = e.y + 20;
          a = aimAngle(gx, gy, w.player);
          fan(w.bullets, gx, gy, a, 5.5 * bs, 3, 0.2, "laser");
        }
        e.fireTimer = interval(30, d);
      }
      if (e.altTimer <= 0) {
        ring(w.bullets, e.x, e.y, 12, 2.0 * bs, e.amp);
        e.amp += 0.25;
        e.altTimer = interval(60, d);
      }
    } else if (e.phaseIndex === 1) {
      if (e.fireTimer <= 0) {
        for (k = 0; k < 4; k++) {
          single(w.bullets, e.x, e.y, e.amp + k * HALF_PI, 2.6 * bs);
          single(w.bullets, e.x, e.y, -e.amp + k * HALF_PI + 0.4, 2.2 * bs);
        }
        e.amp += 0.17;
        e.fireTimer = interval(24, d);
      }
    } else {
      if (e.fireTimer <= 0) {
        ring(w.bullets, e.x, e.y, 18, 2.0 * bs, e.amp, "big");
        e.amp += 0.17;
        e.fireTimer = interval(45, d);
      }
      if (e.altTimer <= 0) {
        a = aimAngle(e.x, e.y, w.player);
        single(w.bullets, e.x, e.y + 30, a, 4.4 * bs);
        e.altTimer = R.FANG_RUSH_SHOT_INTERVAL;
      }
    }
  }

  var UPDATERS = {
    scout: scout, weaver: weaver, diver: diver, gunship: gunship,
    meteor_big: meteor, meteor_medium: meteor, meteor_small: meteor,
    boss_warden: warden, boss_fang: fang
  };
  var SPLITS = { meteor_big: "meteor_medium", meteor_medium: "meteor_small" };

  // ---------------------------------------------------------------- 出怪控制
  var IDLE = 0, WARNING = 1, BOSS_FIGHT = 2;

  function Director() {
    this.state = IDLE;
    this.waveTimer = 90;
    this.warnTimer = 0;
  }

  function spawnBoss(w, kind, x) {
    var hp = R.ENEMIES[kind].hp * (1 + R.BOSS_HP_PER_STAGE * (w.stage - 1));
    hp = Math.max(R.STAT_ROUND, Math.floor(hp / R.STAT_ROUND + 0.5) * R.STAT_ROUND);   // 取整到 50
    var e = new Enemy(kind, x, -60.0, 0, 0, hp);
    e.homeX = x;
    e.targetY = ENTRY_Y[kind];
    e.fireTimer = 40;
    e.altTimer = 70;
    return e;
  }

  Director.prototype.update = function (w) {
    if (this.state === IDLE) {
      if (w.stageFrame >= R.BOSS_TIME) {
        this.state = WARNING;
        this.warnTimer = R.BOSS_WARNING_FRAMES;
        w.emit("warning", R.WIDTH / 2, R.HEIGHT / 2, w.stage);
        return;
      }
      this.waveTimer -= 1;
      if (this.waveTimer <= 0) {
        this.spawnWave(w);
        var base = Math.max(R.WAVE_INTERVAL_MIN, R.WAVE_INTERVAL_START / w.difficulty());
        this.waveTimer = Math.floor(base * w.rng.uniform(0.8, 1.2));
      }
    } else if (this.state === WARNING) {
      this.warnTimer -= 1;
      if (this.warnTimer <= 0) {
        var kind = R.BOSS_ORDER[Math.min(w.stage, R.FINAL_STAGE) - 1];
        if ((R.BOSS_COUNT[kind] || 1) === 2) {
          w.enemies.push(spawnBoss(w, kind, R.WIDTH / 2 - R.TWIN_OFFSET));
          w.enemies.push(spawnBoss(w, kind, R.WIDTH / 2 + R.TWIN_OFFSET));
        } else {
          w.enemies.push(spawnBoss(w, kind, R.WIDTH / 2));
        }
        this.state = BOSS_FIGHT;
      }
    }
  };

  Director.prototype.bossDefeated = function () {
    this.state = IDLE;
    this.waveTimer = 150;
  };

  Director.prototype.spawnWave = function (w) {
    var allowGunship = w.stage > 1 || w.stageFrame > R.GUNSHIP_AFTER;
    var choices = R.WAVES.filter(function (p) { return p[0] !== "gunship" || allowGunship; });
    WAVES[w.rng.weighted(choices)](w);
  };

  var WAVES = {
    scout_line: function (w) {
      var rng = w.rng, n = 3 + rng.randint(0, 2), spacing = R.WIDTH / (n + 1);
      for (var i = 0; i < n; i++) {
        var e = new Enemy("scout", spacing * (i + 1), -30 - 20 * i, 0, 2.2);
        e.fireTimer = rng.randint(30, 90);
        w.enemies.push(e);
      }
    },
    scout_vee: function (w) {
      var rng = w.rng, cx = rng.uniform(140, R.WIDTH - 140);
      for (var i = -2; i < 3; i++) {
        var e = new Enemy("scout", cx + i * 45, -30 - Math.abs(i) * 35, 0, 2.4);
        e.fireTimer = rng.randint(30, 90);
        w.enemies.push(e);
      }
    },
    weavers: function (w) {
      var rng = w.rng, amp = rng.uniform(50, 90), sides = [-1, 1];
      for (var i = 0; i < 2; i++) {
        var side = sides[i];
        var e = new Enemy("weaver", 0, -30, 0, 1.6);
        e.homeX = R.WIDTH / 2 + side * rng.uniform(70, 150);
        e.amp = amp;
        e.phase = side < 0 ? 0 : Math.PI;
        e.x = e.homeX + amp * Math.sin(e.phase);
        e.fireTimer = rng.randint(40, 100);
        w.enemies.push(e);
      }
    },
    divers: function (w) {
      var rng = w.rng, n = rng.randint(2, 3);
      for (var i = 0; i < n; i++) {
        var e = new Enemy("diver", rng.uniform(60, R.WIDTH - 60), -30 - 40 * i, 0, 3.0);
        e.targetY = rng.uniform(70, 200);
        w.enemies.push(e);
      }
    },
    meteors: function (w) {
      var rng = w.rng, n = rng.randint(2, 4);
      for (var i = 0; i < n; i++) {
        var kind = rng.chance(0.4) ? "meteor_big" : "meteor_medium";
        var x = rng.uniform(40, R.WIDTH - 40);
        var y = -40 - rng.uniform(0, 80);
        var vx = rng.uniform(-1.2, 1.2);
        var vy = rng.uniform(1.5, 3.0);
        w.enemies.push(new Enemy(kind, x, y, vx, vy));
      }
    },
    gunship: function (w) {
      var rng = w.rng;
      var e = new Enemy("gunship", rng.uniform(100, R.WIDTH - 100), -40, 0, 1.5);
      e.targetY = rng.uniform(110, 210);
      e.fireTimer = 60;
      e.altTimer = 40;
      w.enemies.push(e);
    }
  };

  // ---------------------------------------------------------------- 整個世界
  function World(seed) {
    this.rng = new S.Rng(seed || 0);
    this.reset(seed || 0);
  }

  World.prototype.reset = function (seed) {
    if (seed !== undefined && seed !== null) this.rng.seed(seed);
    this.player = new Player();
    this.enemies = [];
    this.bullets = [];
    this.shots = [];
    this.items = [];
    this.director = new Director();
    this.events = [];
    this.frame = 0;
    this.stage = 1;
    this.stageFrame = 0;
    this.score = 0;
    this.graze = 0;
    this.done = false;
    this.cleared = false;
  };

  World.prototype.difficulty = function () {
    var progress = Math.min(this.stageFrame / R.BOSS_TIME, 1.0);
    return R.DIFFICULTY_SCALE * (1.0 + R.DIFFICULTY_PER_STAGE * (this.stage - 1) +
                                 R.DIFFICULTY_IN_STAGE * progress);
  };
  World.prototype.bulletSpeed = function () { return 0.85 + 0.15 * this.difficulty(); };
  World.prototype.boss = function () {
    for (var i = 0; i < this.enemies.length; i++) {
      var e = this.enemies[i];
      if (e.isBoss && e.alive) return e;
    }
    return null;
  };
  World.prototype.emit = function (name, x, y, value) {
    this.events.push([name, x, y, value === undefined ? null : value]);
  };

  function alive(o) { return o.alive; }

  World.prototype.step = function (dx, dy, focus, bomb) {
    if (this.done) return 0;
    this.events = [];
    this.frame += 1;
    this.stageFrame += 1;
    var p = this.player, i;

    p.move(dx || 0, dy || 0, !!focus);
    if (bomb && p.bombs > 0) this.bomb(false);
    if (p.invuln > 0) p.invuln -= 1;
    p.fireCooldown -= 1;
    if (p.fireCooldown <= 0) {
      Array.prototype.push.apply(this.shots, p.shots());
      p.fireCooldown = R.FIRE_INTERVAL;
      this.emit("shoot", p.x, p.y, p.power);
    }

    this.director.update(this);
    var snapshot = this.enemies.slice();
    for (i = 0; i < snapshot.length; i++) if (snapshot[i].alive) snapshot[i].update(this);
    for (i = 0; i < this.shots.length; i++) this.shots[i].update();
    for (i = 0; i < this.bullets.length; i++) this.bullets[i].update();
    for (i = 0; i < this.items.length; i++) this.items[i].update(p);

    this.shotsVsEnemies();
    var lost = this.playerCollisions();
    this.pickups();

    this.enemies = this.enemies.filter(alive);
    this.bullets = this.bullets.filter(alive);
    this.shots = this.shots.filter(alive);
    this.items = this.items.filter(alive);
    if (p.hp <= 0) {
      this.done = true;
      this.emit("gameover", p.x, p.y, this.score);
    }
    return lost;
  };

  World.prototype.shotsVsEnemies = function () {
    for (var i = 0; i < this.shots.length; i++) {
      var s = this.shots[i];
      if (!s.alive) continue;
      for (var j = 0; j < this.enemies.length; j++) {     // 長度即時更新，跟 Python 的 for 迴圈行為一樣
        var e = this.enemies[j];
        if (!e.alive || !e.damageable()) continue;
        var dx = e.x - s.x, dy = e.y - s.y, rr = e.radius + R.SHOT_RADIUS;
        if (dx * dx + dy * dy < rr * rr) {
          s.alive = false;
          this.damageEnemy(e, R.SHOT_DAMAGE);
          break;
        }
      }
    }
  };

  World.prototype.damageEnemy = function (e, amount) {
    e.hp -= amount;
    e.flash = 3;
    if (e.hp > 0) { this.emit("hit", e.x, e.y, e.kind); return; }
    e.alive = false;
    this.score += e.score;
    this.emit("explode", e.x, e.y, e.kind);
    var rng = this.rng, i;
    if (e.isBoss) {
      for (i = 0; i < R.BOSS_ITEM_DROPS; i++) {
        var x = e.x + rng.uniform(-60, 60);
        var y = e.y + rng.uniform(-30, 30);
        this.items.push(new Item(x, y, rng.weighted(ITEM_CHOICES)));
      }
      this.cancelBullets(null);
      if (this.lastStageBoss(e)) {
        if (this.stage >= R.FINAL_STAGE) {
          this.allClear(e, true);
        } else {
          this.nextStage();
          this.emit("boss_down", e.x, e.y, this.stage);
        }
      }
      return;
    }
    if (e.drop > 0 && rng.chance(e.drop)) {
      this.items.push(new Item(e.x, e.y, rng.weighted(ITEM_CHOICES)));
    }
    var child = SPLITS[e.kind];
    if (child) {
      for (i = -1; i <= 1; i += 2) {
        this.enemies.push(new Enemy(child, e.x + i * 10, e.y, i * 1.2 + e.vx * 0.5, e.vy));
      }
    }
  };

  World.prototype.bossPhaseChange = function (e, phase, timedOut) {
    e.phaseIndex = phase;
    e.phaseTimer = 0;
    e.fireTimer = 40;
    e.altTimer = 70;
    this.cancelBullets(null);
    if (!timedOut) this.score += R.PHASE_BONUS;
    this.emit("phase", e.x, e.y, [e.kind, phase]);
  };

  World.prototype.bossEscaped = function (e) {
    e.alive = false;
    this.cancelBullets(null);
    if (this.lastStageBoss(e)) {
      if (this.stage >= R.FINAL_STAGE) {
        this.allClear(e, false);
      } else {
        this.nextStage();
        this.emit("escape", e.x, e.y, this.stage);
      }
    }
  };

  World.prototype.lastStageBoss = function (gone) {
    var others = this.enemies.filter(function (o) {
      return o !== gone && o.alive && o.isBoss;
    });
    for (var i = 0; i < others.length; i++) {
      if (!others[i].rage) {
        others[i].rage = true;
        this.emit("rage", others[i].x, others[i].y, others[i].kind);
      }
    }
    return others.length === 0;
  };

  World.prototype.allClear = function (e, defeated) {
    if (defeated) {
      this.cleared = true;
      this.score += R.CLEAR_BONUS + R.CLEAR_BONUS_PER_HP * this.player.hp;
    }
    this.done = true;
    this.emit("clear", e.x, e.y, defeated);
  };

  World.prototype.nextStage = function () {
    this.stage += 1;
    this.stageFrame = 0;
    this.director.bossDefeated();
  };

  World.prototype.playerCollisions = function () {
    var p = this.player, lost = 0, i, dx, dy, rr;
    for (i = 0; i < this.bullets.length; i++) {
      var b = this.bullets[i];
      if (!b.alive) continue;
      dx = b.x - p.x; dy = b.y - p.y;
      var d2 = dx * dx + dy * dy;
      rr = R.PLAYER_RADIUS + b.r;
      if (d2 < rr * rr) {
        if (p.invuln === 0) {
          b.alive = false;
          lost += this.hitPlayer();
        }
      } else if (!b.grazed) {
        var gr = R.PLAYER_GRAZE_RADIUS + b.r;
        if (d2 < gr * gr) {
          b.grazed = true;
          this.graze += 1;
          this.score += R.GRAZE_SCORE;
          this.emit("graze", b.x, b.y);
        }
      }
    }
    for (i = 0; i < this.enemies.length; i++) {
      var e = this.enemies[i];
      if (!e.alive) continue;
      dx = e.x - p.x; dy = e.y - p.y;
      rr = R.PLAYER_RADIUS + e.radius * R.ENEMY_CONTACT_SCALE;
      if (dx * dx + dy * dy < rr * rr && p.invuln === 0) {
        if (!e.isBoss) this.damageEnemy(e, R.CONTACT_DAMAGE_TO_ENEMY);
        lost += this.hitPlayer();
      }
    }
    return lost;
  };

  World.prototype.hitPlayer = function () {
    var p = this.player;
    if (p.invuln > 0) return 0;
    if (p.shield) {
      p.shield = false;
      p.invuln = R.SHIELD_INVULN_FRAMES;
      this.cancelBullets(90.0);
      this.emit("shield", p.x, p.y);
      return 0;
    }
    if (R.AUTO_BOMB && p.bombs > 0) { this.bomb(true); return 0; }
    p.hp -= 1;
    p.power = Math.max(1, p.power - 1);
    p.invuln = R.INVULN_FRAMES;
    this.emit("hurt", p.x, p.y, p.hp);
    return 1;
  };

  World.prototype.bomb = function (auto) {
    var p = this.player;
    p.bombs -= 1;
    p.invuln = Math.max(p.invuln, R.BOMB_INVULN_FRAMES);
    this.emit("bomb", p.x, p.y, auto);
    this.cancelBullets(null);
    var snapshot = this.enemies.slice();
    for (var i = 0; i < snapshot.length; i++) {
      var e = snapshot[i];
      if (e.alive && e.damageable()) this.damageEnemy(e, R.BOMB_DAMAGE);
    }
  };

  World.prototype.cancelBullets = function (radius) {
    var p = this.player;
    for (var i = 0; i < this.bullets.length; i++) {
      var b = this.bullets[i];
      if (!b.alive) continue;
      if (radius !== null) {
        var dx = b.x - p.x, dy = b.y - p.y;
        if (dx * dx + dy * dy > radius * radius) continue;
      }
      b.alive = false;
      this.score += R.BULLET_CANCEL_SCORE;
      this.emit("cancel", b.x, b.y);
    }
  };

  World.prototype.pickups = function () {
    var p = this.player, rr = R.ITEM_PICKUP_RADIUS * R.ITEM_PICKUP_RADIUS;
    for (var i = 0; i < this.items.length; i++) {
      var it = this.items[i];
      if (!it.alive) continue;
      var dx = it.x - p.x, dy = it.y - p.y;
      if (dx * dx + dy * dy >= rr) continue;
      it.alive = false;
      var k = it.kind;
      if (k === R.ITEM_POWER) {
        if (p.power < R.PLAYER_MAX_POWER) p.power += 1; else this.score += 200;
      } else if (k === R.ITEM_HEAL) {
        p.hp = Math.min(p.hp + 1, R.PLAYER_MAX_HP);
      } else if (k === R.ITEM_SHIELD) {
        p.shield = true;
      } else if (k === R.ITEM_BOMB) {
        p.bombs = Math.min(p.bombs + 1, R.PLAYER_MAX_BOMBS);
      } else {
        this.score += R.ITEM_SCORE_VALUE;
      }
      this.emit("pickup", it.x, it.y, k);
    }
  };

  S.World = World;
  S.Director = { IDLE: IDLE, WARNING: WARNING, BOSS_FIGHT: BOSS_FIGHT };
})(this.Shmup = this.Shmup || {});
