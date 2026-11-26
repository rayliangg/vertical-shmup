// Canvas 2D 繪圖：背景、角色、粒子、HUD、agent 視角。
(function (S) {
  "use strict";
  var R = S.RULES;
  var ASSET_ROOT = "../assets/images/";
  var IMAGES = {
    ship: "player/ship.png", life: "ui/life.png",
    scout: "enemies/scout.png", weaver: "enemies/weaver.png", diver: "enemies/diver.png",
    gunship: "enemies/gunship.png",
    boss_warden: "enemies/boss_warden.png",
    boss_fang: "enemies/boss_fang.png",
    meteor_big: "enemies/meteor_big.png", meteor_medium: "enemies/meteor_medium.png",
    meteor_small: "enemies/meteor_small.png",
    laser: "projectiles/player_laser.png", laser_max: "projectiles/player_laser_max.png",
    enemy_laser: "projectiles/enemy_laser.png", shield: "effects/shield.png",
    item0: "items/power.png", item1: "items/heal.png", item2: "items/shield.png",
    item3: "items/bomb.png", item4: "items/score.png",
    bg0: "backgrounds/dark_purple.png", bg1: "backgrounds/blue.png",
    bg2: "backgrounds/purple.png", bg3: "backgrounds/black.png"
  };
  var ENEMY_WIDTH_SCALE = 2.7;
  var PANEL_W = 280;                 // 右邊資訊面板的寬度
  var ITEM_COLORS = ["#ffd23c", "#5aff78", "#6ec8ff", "#ff5a5a", "#fff096"];
  var ITEM_LABELS = ["POWER UP", "+1 HP", "SHIELD", "+1 BOMB", "+500"];
  var BULLET_COLORS = { orb: [255, 70, 130], big: [180, 90, 255] };
  var FONT = "'KenVector', 'Trebuchet MS', sans-serif";

  function rand(a, b) { return a + Math.random() * (b - a); }

  function Renderer(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.images = {};
    this.glows = {};
    this.particles = [];
    this.rings = [];
    this.popups = [];
    this.shake = 0;
    this.flash = 0;
    this.bank = 0;
    this.tick = 0;
    this.scroll = 0;
    this.banner = null;
    this.subtitle = null;
    this.showAgentView = false;
    this.stars = [];
    for (var i = 0; i < 95; i++) {
      var near = i >= 60;
      this.stars.push({ x: rand(0, R.WIDTH), y: rand(0, R.HEIGHT),
                        v: (near ? 2.6 : 1.2) * rand(0.8, 1.2), s: near ? 2 : 1,
                        a: near ? 0.8 : 0.45 });
    }
  }

  Renderer.prototype.load = function (done) {
    var keys = Object.keys(IMAGES), left = keys.length, self = this;
    keys.forEach(function (k) {
      var img = new Image();
      img.onload = img.onerror = function () { if (--left === 0) done(); };
      img.src = ASSET_ROOT + IMAGES[k];
      self.images[k] = img;
    });
  };

  Renderer.prototype.glow = function (radius, kind) {
    var key = kind + radius, c = this.glows[key];
    if (c) return c;
    var col = BULLET_COLORS[kind], size = radius * 4;
    c = document.createElement("canvas");
    c.width = c.height = size;
    var g = c.getContext("2d"), mid = size / 2;
    var grad = g.createRadialGradient(mid, mid, 0, mid, mid, mid);
    grad.addColorStop(0, "rgba(255,255,255,1)");
    grad.addColorStop(0.22, "rgba(255,255,255,1)");
    grad.addColorStop(0.3, "rgba(" + col + ",1)");
    grad.addColorStop(0.5, "rgba(" + col + ",0.35)");
    grad.addColorStop(1, "rgba(" + col + ",0)");
    g.fillStyle = grad;
    g.fillRect(0, 0, size, size);
    this.glows[key] = c;
    return c;
  };

  // ------------------------------------------------------------------ 特效
  Renderer.prototype.sparks = function (x, y, color, count, speed, life, size) {
    for (var i = 0; i < count && this.particles.length < 600; i++) {
      var a = rand(0, Math.PI * 2), s = rand(0.3, 1) * speed, n = Math.floor(rand(life * 0.6, life));
      this.particles.push({ x: x, y: y, vx: Math.cos(a) * s, vy: Math.sin(a) * s,
                            life: n, max: n, size: size, color: color });
    }
  };
  Renderer.prototype.ring = function (x, y, color, speed, life, width) {
    this.rings.push({ x: x, y: y, r: 4, speed: speed, life: life, max: life, color: color, w: width });
  };
  Renderer.prototype.explosion = function (x, y, big) {
    var k = big ? 2.2 : 1;
    this.ring(x, y, "255,220,160", 5 * k, Math.floor(18 * k), 3);
    this.sparks(x, y, "255,200,80", Math.floor(16 * k), 5 * k, Math.floor(28 * k), 3);
    this.sparks(x, y, "255,90,40", Math.floor(10 * k), 3 * k, Math.floor(36 * k), 4);
    this.sparks(x, y, "255,255,255", Math.floor(6 * k), 7 * k, 12, 2);
    this.shake = Math.max(this.shake, big ? 9 : 2.5);
    if (big) this.flash = 10;
  };

  Renderer.prototype.reset = function () {
    this.particles = []; this.rings = []; this.popups = [];
    this.shake = 0; this.flash = 0;
    this.subtitle = null;
    this.banner = { text: "STAGE 1", left: 120, color: "#ffe65a" };
  };

  Renderer.prototype.handleEvents = function (events) {
    for (var i = 0; i < events.length; i++) {
      var ev = events[i], name = ev[0], x = ev[1], y = ev[2], v = ev[3];
      if (name === "explode") {
        this.explosion(x, y, R.ENEMIES[v].boss === true);
        if (v === "gunship" || v === "meteor_big") this.shake = Math.max(this.shake, 5);
      } else if (name === "hit") {
        this.sparks(x, y, "255,255,200", 3, 3, 10, 2);
      } else if (name === "hurt") {
        this.shake = Math.max(this.shake, 12);
        this.sparks(x, y, "255,80,80", 20, 6, 30, 3);
        this.ring(x, y, "255,80,80", 6, 20, 4);
      } else if (name === "shield") {
        this.ring(x, y, "120,200,255", 8, 22, 5);
      } else if (name === "bomb") {
        this.ring(x, y, "255,255,255", 14, 40, 8);
        this.ring(x, y, "255,120,120", 10, 45, 4);
        this.flash = 8;
        this.shake = Math.max(this.shake, 8);
        this.banner = { text: v ? "AUTO BOMB" : "BOMB", left: 50, color: "#ff7878" };
      } else if (name === "cancel") {
        this.sparks(x, y, "255,240,150", 2, 1.5, 20, 2);
      } else if (name === "graze") {
        this.sparks(x, y, "200,220,255", 2, 2, 8, 2);
      } else if (name === "pickup") {
        this.sparks(x, y, "255,255,255", 10, 3, 20, 2);
        this.popups.push({ text: ITEM_LABELS[v], color: ITEM_COLORS[v], x: x, y: y - 16, life: 50 });
      } else if (name === "warning") {
        this.banner = { text: "WARNING", left: R.BOSS_WARNING_FRAMES, color: "#ff3c3c" };
      } else if (name === "boss") {
        this.banner = { text: R.BOSS_NAMES[v], left: 100, color: "#ff7878" };
      } else if (name === "phase") {
        this.subtitle = { text: "PHASE " + (v[1] + 1) + "  " + R.PHASE_NAMES[v[0]][v[1]].toUpperCase(),
                          left: 150 };
      } else if (name === "boss_down") {
        this.banner = { text: "STAGE " + v, left: 150, color: "#ffe65a" };
        this.subtitle = null;
      } else if (name === "clear") {
        this.banner = { text: v ? "ALL CLEAR" : "BOSS ESCAPED", left: 600, color: "#ffe65a" };
        this.subtitle = null;
      } else if (name === "rage") {
        this.banner = { text: "RAGE MODE", left: 90, color: "#ff5050" };
      } else if (name === "escape") {
        this.banner = { text: "BOSS ESCAPED", left: 120, color: "#c8c8ff" };
        this.subtitle = null;
      }
    }
  };

  Renderer.prototype.updateEffects = function () {
    var i, p;
    var keep = [];
    for (i = 0; i < this.particles.length; i++) {
      p = this.particles[i];
      if (--p.life > 0) { p.vx *= 0.9; p.vy *= 0.9; p.x += p.vx; p.y += p.vy; keep.push(p); }
    }
    this.particles = keep;
    this.rings = this.rings.filter(function (g) { g.r += g.speed; return --g.life > 0; });
    this.popups = this.popups.filter(function (t) { t.y -= 0.8; return --t.life > 0; });
    this.shake *= 0.85;
    if (this.shake < 0.3) this.shake = 0;
    if (this.flash) this.flash -= 1;
  };

  // ------------------------------------------------------------------ 繪圖
  Renderer.prototype.sprite = function (key, x, y, width, angle, alpha) {
    var img = this.images[key];
    if (!img || !img.width) return;
    var w = width || img.width, h = img.height * w / img.width, ctx = this.ctx;
    if (alpha !== undefined) ctx.globalAlpha = alpha;
    if (angle) {
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(angle);
      ctx.drawImage(img, -w / 2, -h / 2, w, h);
      ctx.restore();
    } else {
      ctx.drawImage(img, x - w / 2, y - h / 2, w, h);
    }
    if (alpha !== undefined) ctx.globalAlpha = 1;
  };

  Renderer.prototype.text = function (str, size, x, y, color, align, baseline) {
    var ctx = this.ctx;
    ctx.font = size + "px " + FONT;
    ctx.textAlign = align || "center";
    ctx.textBaseline = baseline || "top";
    ctx.fillStyle = "rgba(0,0,0,0.8)";
    ctx.fillText(str, x + 2, y + 2);
    ctx.fillStyle = color || "#fff";
    ctx.fillText(str, x, y);
  };

  Renderer.prototype.draw = function (world, overlay, hud) {
    var ctx = this.ctx, i;
    this.tick += 1;
    var boost = world.director.state === S.Director.WARNING ? 3 : 1;

    ctx.save();
    ctx.beginPath(); ctx.rect(0, 0, R.WIDTH, R.HEIGHT); ctx.clip();   // 震動時不要蓋到面板
    ctx.fillStyle = "#000"; ctx.fillRect(0, 0, R.WIDTH, R.HEIGHT);
    if (this.shake) ctx.translate(rand(-this.shake, this.shake), rand(-this.shake, this.shake));
    // 背景圖 + 星星
    var bg = this.images["bg" + ((world.stage - 1) % 4)];
    this.scroll = (this.scroll + 0.6 * boost) % 256;
    if (bg && bg.width) {
      for (var ty = this.scroll - 256; ty < R.HEIGHT; ty += 256)
        for (var tx = 0; tx < R.WIDTH; tx += 256) ctx.drawImage(bg, tx, ty);
    }
    for (i = 0; i < this.stars.length; i++) {
      var s = this.stars[i];
      s.y += s.v * boost;
      if (s.y > R.HEIGHT) { s.y = -2; s.x = rand(0, R.WIDTH); }
      ctx.fillStyle = "rgba(220,230,255," + s.a + ")";
      ctx.fillRect(s.x, s.y, s.s, s.s + 1);
    }

    this.drawItems(world);
    this.drawShots(world);
    this.drawEnemies(world);
    this.drawPlayer(world.player);
    this.drawBullets(world);
    this.updateEffects();
    this.drawEffects();
    ctx.restore();

    ctx.save();
    ctx.beginPath(); ctx.rect(0, 0, R.WIDTH, R.HEIGHT); ctx.clip();
    if (this.flash) {
      ctx.fillStyle = "rgba(255,255,255," + (0.07 * this.flash) + ")";
      ctx.fillRect(0, 0, R.WIDTH, R.HEIGHT);
    }
    if (this.showAgentView && overlay) this.drawAgentView(world, overlay);
    this.drawPlayfieldHud(world);
    ctx.restore();
    this.drawPanel(world, hud || {});
  };

  Renderer.prototype.drawPlayer = function (p) {
    var ctx = this.ctx;
    this.bank += (p.moveX * -0.24 - this.bank) * 0.25;
    var cx = p.x, cy = p.y + R.PLAYER_HALF_H - 4, flick = 10 + (this.tick % 4) * 3;
    ctx.fillStyle = "#ff9628";
    ctx.beginPath(); ctx.moveTo(cx - 6, cy); ctx.lineTo(cx + 6, cy); ctx.lineTo(cx, cy + flick); ctx.fill();
    ctx.fillStyle = "#fff0a0";
    ctx.beginPath(); ctx.moveTo(cx - 3, cy); ctx.lineTo(cx + 3, cy); ctx.lineTo(cx, cy + flick / 2); ctx.fill();
    var blink = p.invuln && Math.floor(p.invuln / 4) % 2;
    if (!blink) this.sprite("ship", p.x, p.y, R.PLAYER_HALF_W * 2, this.bank);
    if (p.shield) {
      this.sprite("shield", p.x, p.y - 4, 74 + 4 * Math.sin(this.tick * 0.2), 0, 0.67);
    }
    if (p.focus || this.showAgentView) {
      ctx.beginPath(); ctx.arc(p.x, p.y, R.PLAYER_RADIUS + 2, 0, Math.PI * 2);
      ctx.fillStyle = "#ff3c3c"; ctx.fill();
      ctx.beginPath(); ctx.arc(p.x, p.y, R.PLAYER_RADIUS, 0, Math.PI * 2);
      ctx.fillStyle = "#fff"; ctx.fill();
    }
  };

  Renderer.prototype.drawEnemies = function (world) {
    var ctx = this.ctx;
    for (var i = 0; i < world.enemies.length; i++) {
      var e = world.enemies[i], w = e.radius * ENEMY_WIDTH_SCALE, angle = 0, x = e.x;
      if (e.kind.indexOf("meteor") === 0) angle = ((e.age * 3 + e.homeX) % 360) * Math.PI / 180;
      if (e.kind === "diver" && e.state === 1) x += rand(-2, 2);
      this.sprite(e.kind, x, e.y, w, angle);
      if (e.flash) {
        ctx.globalCompositeOperation = "lighter";
        this.sprite(e.kind, x, e.y, w, angle, 0.45);
        ctx.globalCompositeOperation = "source-over";
      }
    }
  };

  Renderer.prototype.drawBullets = function (world) {
    var ctx = this.ctx;
    for (var i = 0; i < world.bullets.length; i++) {
      var b = world.bullets[i];
      if (b.kind === "laser") {
        this.sprite("enemy_laser", b.x, b.y, 9, Math.atan2(b.vy, b.vx) + Math.PI / 2);
      } else {
        var g = this.glow(b.r, b.kind);
        ctx.drawImage(g, b.x - g.width / 2, b.y - g.height / 2);
      }
    }
  };

  Renderer.prototype.drawShots = function (world) {
    var key = world.player.power >= R.PLAYER_MAX_POWER ? "laser_max" : "laser";
    for (var i = 0; i < world.shots.length; i++) {
      var s = world.shots[i];
      this.sprite(key, s.x, s.y, 8, Math.atan2(s.vx, -s.vy));
    }
  };

  Renderer.prototype.drawItems = function (world) {
    var ctx = this.ctx;
    for (var i = 0; i < world.items.length; i++) {
      var it = world.items[i], bob = 3 * Math.sin((it.age + it.x) * 0.12);
      ctx.strokeStyle = ITEM_COLORS[it.kind];
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(it.x, it.y + bob, R.ITEM_RADIUS + 3 + 2 * Math.sin(this.tick * 0.2), 0, Math.PI * 2);
      ctx.stroke();
      this.sprite("item" + it.kind, it.x, it.y + bob, 24);
    }
  };

  Renderer.prototype.drawEffects = function () {
    var ctx = this.ctx, i;
    for (i = 0; i < this.particles.length; i++) {
      var p = this.particles[i], k = p.life / p.max, s = Math.max(1, p.size * (0.4 + 0.6 * k));
      ctx.fillStyle = "rgba(" + p.color + "," + k + ")";
      ctx.fillRect(p.x - s / 2, p.y - s / 2, s, s);
    }
    for (i = 0; i < this.rings.length; i++) {
      var g = this.rings[i], kk = g.life / g.max;
      ctx.strokeStyle = "rgba(" + g.color + "," + kk + ")";
      ctx.lineWidth = Math.max(1, g.w * kk);
      ctx.beginPath(); ctx.arc(g.x, g.y, g.r, 0, Math.PI * 2); ctx.stroke();
    }
    for (i = 0; i < this.popups.length; i++) {
      var t = this.popups[i];
      ctx.globalAlpha = Math.min(1, t.life / 30);
      this.text(t.text, 12, t.x, t.y, t.color, "center", "middle");
      ctx.globalAlpha = 1;
    }
  };

  Renderer.prototype.drawAgentView = function (world, overlay) {
    var ctx = this.ctx, F = S.Features, p = world.player, obs = overlay.obs;
    var x0 = p.x - F.CELL * F.GRID / 2, y0 = p.y - F.CELL * F.GRID / 2;
    for (var gy = 0; gy < F.GRID; gy++) {
      for (var gx = 0; gx < F.GRID; gx++) {
        var v = obs[F.OFF_GRID + gy * F.GRID + gx];
        var rx = x0 + gx * F.CELL, ry = y0 + gy * F.CELL;
        if (v > 0) {
          ctx.fillStyle = "rgba(255,40,40," + (0.16 + 0.47 * v) + ")";
          ctx.fillRect(rx, ry, F.CELL - 1, F.CELL - 1);
        } else {
          ctx.strokeStyle = "rgba(80,200,255,0.18)";
          ctx.lineWidth = 1;
          ctx.strokeRect(rx + 0.5, ry + 0.5, F.CELL - 2, F.CELL - 2);
        }
      }
    }
    if (overlay.probs) {
      var a = F.ACTIONS[overlay.action];
      ctx.strokeStyle = "#50ff78";
      ctx.lineWidth = 3;
      ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(p.x + a[0] * 40, p.y + a[1] * 40); ctx.stroke();
      if (a[2]) this.text("FOCUS", 11, p.x, p.y + 40, "#50ff78");
    }
  };

  // ---- 遊戲區裡的 HUD：魔王血條、階段名稱、ENEMY 標記、標題帶 ----
  Renderer.prototype.drawPlayfieldHud = function (world) {
    var ctx = this.ctx, i;
    var bosses = world.enemies.filter(function (e) { return e.isBoss && e.alive && e.state > 0; });
    for (i = 0; i < Math.min(bosses.length, 2); i++) {
      var boss = bosses[i];
      this.drawBossBar(boss, 22 + i * 20);
      var mx = Math.min(Math.max(boss.x, 14), R.WIDTH - 14);   // ENEMY 標記
      ctx.fillStyle = "#ff465a";
      ctx.beginPath(); ctx.moveTo(mx - 7, R.HEIGHT); ctx.lineTo(mx + 7, R.HEIGHT);
      ctx.lineTo(mx, R.HEIGHT - 9); ctx.fill();
      this.text("ENEMY", 9, mx, R.HEIGHT - 22, "#ff7882");
    }
    if (this.subtitle) {
      this.text(this.subtitle.text, 13, R.WIDTH - 10, 26 + 20 * Math.min(bosses.length, 2),
                "#ffc878", "right");
      if (--this.subtitle.left <= 0) this.subtitle = null;
    }
    if (this.banner) {
      var b = this.banner, y = R.HEIGHT / 3;
      if (Math.floor(b.left / 12) % 2 === 0 || b.text !== "WARNING") {
        ctx.fillStyle = b.text === "WARNING" ? "rgba(120,0,0,0.6)" : "rgba(0,0,0,0.6)";
        ctx.fillRect(0, y - 32, R.WIDTH, 64);
        ctx.fillStyle = b.color;
        ctx.fillRect(0, y - 32, R.WIDTH, 2);
        ctx.fillRect(0, y + 30, R.WIDTH, 2);
        this.text(b.text, 30, R.WIDTH / 2, y, b.color, "center", "middle");
      }
      b.left -= 1;
      if (b.left <= 0) this.banner = null;
    }
  };

  Renderer.prototype.drawBossBar = function (boss, y) {
    var ctx = this.ctx, x = 10, w = R.WIDTH - 60;
    this.text(R.BOSS_NAMES[boss.kind], 10, x, y - 13, "#ff9696", "left");
    if (boss.rage) this.text("RAGE", 10, x + w, y - 13, "#ff5050", "right");
    ctx.fillStyle = "#3c141e"; ctx.fillRect(x, y, w, 6);
    ctx.fillStyle = "#ff465a"; ctx.fillRect(x, y, w * Math.max(boss.hp, 0) / boss.maxHp, 6);
    ctx.strokeStyle = "#fff"; ctx.lineWidth = 1; ctx.strokeRect(x + 0.5, y + 0.5, w, 6);
    {
      R.PHASE_THRESHOLDS.forEach(function (t) {
        ctx.beginPath(); ctx.moveTo(x + w * t, y - 2); ctx.lineTo(x + w * t, y + 8); ctx.stroke();
      });
      var left = Math.floor(Math.max(0, R.BOSS_PHASE_TIME - boss.phaseTimer) / R.FPS);
      this.text(("0" + left).slice(-2), 14, R.WIDTH - 8, y - 6, "#ffe696", "right");
    }
  };

  // ---- 右邊的資訊面板（彈幕遊戲常見的版面） ----
  Renderer.prototype.drawPanel = function (world, hud) {
    var ctx = this.ctx, x0 = R.WIDTH, W = PANEL_W, cx = x0 + W / 2, i, p = world.player;
    var lx = x0 + 22, rx = x0 + W - 22, self = this;
    var bg = this.images.bg3;
    ctx.save();
    ctx.beginPath(); ctx.rect(x0, 0, W, R.HEIGHT); ctx.clip();
    if (bg && bg.width) {
      for (var ty = 0; ty < R.HEIGHT; ty += 256) for (var tx = x0; tx < x0 + W; tx += 256) ctx.drawImage(bg, tx, ty);
    }
    ctx.fillStyle = "rgba(10,10,30,0.47)"; ctx.fillRect(x0, 0, W, R.HEIGHT);
    ctx.restore();
    ctx.fillStyle = "#14141c"; ctx.fillRect(x0, 0, 8, R.HEIGHT);
    ctx.fillStyle = "#9696aa"; ctx.fillRect(x0 + 8, 0, 2, R.HEIGHT);
    ctx.strokeStyle = "#5a5a6e"; ctx.lineWidth = 1;
    ctx.strokeRect(x0 + 14.5, 90.5, W - 26, 270);
    ctx.strokeRect(x0 + 14.5, 380.5, W - 26, 230);

    this.text("VERTICAL", 22, cx, 24, "#ffe65a");
    this.text("SHMUP", 22, cx, 50, "#ffe65a");
    function row(y, label, value, color) {
      self.text(label, 13, lx, y, "#aabeff", "left");
      if (value !== undefined && value !== null) self.text(value, 15, rx, y - 1, color || "#fff", "right");
    }
    function pad(n) { return ("000000000" + n).slice(-9); }
    row(110, "HI-SCORE", pad(Math.max(hud.hiscore || 0, world.score)), "#fff096");
    row(140, "SCORE", pad(world.score));
    row(190, "PLAYER");
    for (i = 0; i < R.PLAYER_MAX_HP; i++) this.sprite("life", lx + 102 + i * 24, 199, 20, 0, i < p.hp ? 1 : 0.25);
    row(220, "BOMB");
    for (i = 0; i < R.PLAYER_MAX_BOMBS; i++) this.sprite("item3", lx + 101 + i * 24, 228, 18, 0, i < p.bombs ? 1 : 0.25);
    row(250, "POWER", p.power >= R.PLAYER_MAX_POWER ? "MAX" : null, "#ffd23c");
    for (i = 0; i < R.PLAYER_MAX_POWER; i++) {
      ctx.fillStyle = i < p.power ? "#ffd23c" : "#3c3c50";
      ctx.fillRect(lx + 92 + i * 22, 255, 18, 8);
    }
    row(280, "GRAZE", String(world.graze));
    row(310, "STAGE", String(world.stage));
    if (p.shield) this.text("SHIELD ON", 12, lx, 340, "#78c8ff", "left");
    if (hud.autopilot) {
      this.text("AUTOPILOT", 15, cx, 400, "#50ff78");
      this.drawJoystick(cx, 470, hud.action);
    }
    if (hud.label) this.text(hud.label, 15, cx, 560, "#ffc878");
    this.text("PPO AUTOPILOT DEMO", 10, cx, R.HEIGHT - 30, "#6e6e8c");
  };

  // 3x3 搖桿燈號：亮起來的那格是 AI 選的方向，SLOW 燈表示慢速
  Renderer.prototype.drawJoystick = function (cx, cy, action) {
    var ctx = this.ctx, a = action === null || action === undefined ? null : S.Features.ACTIONS[action];
    for (var gy = -1; gy <= 1; gy++) {
      for (var gx = -1; gx <= 1; gx++) {
        var on = a && a[0] === gx && a[1] === gy;
        var x = cx - 45 + (gx + 1) * 30 - 12, y = cy + gy * 30 - 12;
        ctx.fillStyle = on ? "#3cdc55" : "#282832"; ctx.fillRect(x, y, 26, 26);
        ctx.strokeStyle = on ? "#b4ffbe" : "#50505f"; ctx.lineWidth = 2; ctx.strokeRect(x + 1, y + 1, 24, 24);
      }
    }
    var slow = !!(a && a[2]);
    ctx.fillStyle = slow ? "#ff9628" : "#282832"; ctx.fillRect(cx + 60, cy - 12, 52, 24);
    ctx.strokeStyle = "#5a5a64"; ctx.strokeRect(cx + 61, cy - 11, 50, 22);
    this.text("SLOW", 11, cx + 86, cy, slow ? "#000" : "#6e6e78", "center", "middle");
  };

  Renderer.PANEL_W = PANEL_W;
  S.Renderer = Renderer;
})(this.Shmup = this.Shmup || {});
