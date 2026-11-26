// 網頁版的進入點：音效、主迴圈、輸入、右側面板。

// 用 <audio> 播音效和音樂（瀏覽器規定要先點一下或按鍵才能出聲）。
(function (S) {
  "use strict";
  var ROOT = "../assets/sounds/";
  var SFX = {
    explode: ["explosion", 0.35], hurt: ["hurt", 0.6], shield: ["shield_down", 0.6],
    bomb: ["bomb", 0.7], pickup: ["pickup", 0.35], warning: ["warning", 0.7],
    boss_down: ["stage_clear", 0.7], gameover: ["game_over", 0.7]
  };

  function Audio_() {
    this.enabled = true;
    this.started = false;
    this.volleys = 0;
    this.pool = {};
    this.music = new Audio(ROOT + "music/orbital_colossus.mp3");
    this.music.loop = true;
    this.music.volume = 0.35;
  }

  Audio_.prototype.start = function () {
    if (this.started || !this.enabled) return;
    this.started = true;
    var p = this.music.play();
    if (p && p.catch) p.catch(function () {});
  };

  Audio_.prototype.toggle = function () {
    this.enabled = !this.enabled;
    if (this.enabled) { this.started = false; this.start(); } else { this.music.pause(); }
    return this.enabled;
  };

  Audio_.prototype.play = function (name, volume) {
    if (!this.enabled || !this.started) return;
    var list = this.pool[name] || (this.pool[name] = []);
    var a = null;
    for (var i = 0; i < list.length; i++) if (list[i].paused || list[i].ended) { a = list[i]; break; }
    if (!a) {
      if (list.length >= 4) return;
      a = new Audio(ROOT + "sfx/" + name + ".ogg");
      list.push(a);
    }
    a.volume = volume;
    a.currentTime = 0;
    var p = a.play();
    if (p && p.catch) p.catch(function () {});
  };

  Audio_.prototype.handle = function (events) {
    var played = {};
    for (var i = 0; i < events.length; i++) {
      var name = events[i][0], value = events[i][3];
      if (name === "shoot") {
        if (++this.volleys % 3 === 0) this.play("shoot", 0.12);
      } else if (name === "pickup" && value === 2) {
        this.play("shield_up", 0.5);
      } else if (SFX[name] && !played[name]) {
        played[name] = true;
        this.play(SFX[name][0], SFX[name][1]);
      }
    }
  };

  S.Audio = Audio_;
})(this.Shmup = this.Shmup || {});

// 網頁版進入點：固定時間步長的主迴圈、輸入、場景、右側 demo 面板。
(function (S) {
  "use strict";
  var R = S.RULES, F = S.Features;
  var FRAME_SKIP = 2;                        // agent 每 2 個 frame 決定一次，跟訓練時一樣
  var STEP_MS = 1000 / R.FPS;

  var canvas = document.getElementById("game");
  var renderer = new S.Renderer(canvas);
  var audio = new S.Audio();
  var world = new S.World(Date.now() % 100000);
  var models = S.MODEL_LIST || [];          // 由 web/model/manifest.js 提供（訓練時自動更新）
  var policy = null;

  var state = {
    scene: "title", autopilot: false, speed: 1, action: 0, overlay: null,
    keys: {}, bomb: false, overTimer: 0,
    best: readBest(), runs: [], obs: new Float64Array(F.OBS_DIM)
  };

  // ------------------------------------------------------------- 最高分存檔
  function readBest() {
    try { return parseInt(localStorage.getItem("shmup.best") || "0", 10) || 0; }
    catch (e) { return 0; }
  }
  function writeBest(v) {
    try { localStorage.setItem("shmup.best", String(v)); } catch (e) { /* private mode */ }
  }

  // ------------------------------------------------------------- 右側面板
  var $ = function (id) { return document.getElementById(id); };
  function setAutopilot(on) {
    state.autopilot = !!(on && policy);
    $("btn-autopilot").classList.toggle("on", state.autopilot);
    $("btn-autopilot").textContent = state.autopilot ? "AI 開車中" : "AI 開車";
  }
  function setSpeed(v) {
    state.speed = v;
    Array.prototype.forEach.call(document.querySelectorAll("[data-speed]"), function (b) {
      b.classList.toggle("on", Number(b.getAttribute("data-speed")) === v);
    });
  }
  function setMuted(muted) {
    $("btn-mute").textContent = muted ? "靜音中" : "音效";
    $("btn-mute").classList.toggle("on", muted);
  }
  function setAgentView(on) {
    renderer.showAgentView = on;
    $("btn-view").classList.toggle("on", on);
  }

  // ---- 模型選單：第 100 / 500 / 2000 / 5000 回合、最佳模型 ----
  function describe(entry) {
    var ev = entry.eval || {}, parts = [];
    parts.push("練了 " + Number(entry.step || 0).toLocaleString() + " 步");
    if (ev.seconds != null) {
      parts.push("測試平均撐 " + Math.round(ev.seconds) + " 秒、平均第 " + Number(ev.stage).toFixed(1) +
                 " 關、通關 " + ev.clears + "/" + ev.episodes);
    }
    return parts.join("<br>");
  }

  function selectModel(index) {
    var entry = models[index];
    $("model-info").innerHTML = "載入中…";
    $("btn-autopilot").disabled = true;
    S.loadModel(entry, function (p) {
      policy = p;
      $("btn-autopilot").disabled = !policy;
      $("model-info").innerHTML = policy ? describe(entry) : "這個模型載入失敗，請重新執行 python -m shmup export";
      state.runs = [];                                   // 換模型之後重新統計平均分數
      if (!policy) setAutopilot(false);
      else if (state.autopilot) newGame();
    });
  }

  function initModels() {
    var sel = $("model-select");
    if (!models.length) {
      sel.disabled = true;
      sel.innerHTML = "<option>還沒有模型</option>";
      $("model-info").innerHTML = "先訓練（python -m shmup train），<br>每到一個里程碑就會自動出現在這裡";
      $("btn-autopilot").disabled = true;
      return;
    }
    var preferred = 0;
    models.forEach(function (entry, i) {
      var opt = document.createElement("option");
      opt.value = String(i);
      opt.textContent = entry.label;
      sel.appendChild(opt);
      if (entry.id !== "best") preferred = i;            // 預設選最後一個里程碑（練最久的）
    });
    sel.value = String(preferred);
    sel.onchange = function () { selectModel(Number(sel.value)); canvas.focus(); };
    selectModel(preferred);
  }

  function initPanel() {
    initModels();
    $("btn-play").onclick = function () { setAutopilot(false); newGame(); canvas.focus(); };
    $("btn-autopilot").onclick = function () {
      setAutopilot(!state.autopilot);
      if (state.autopilot && state.scene !== "playing") newGame();
      canvas.focus();
    };
    $("btn-view").onclick = function () { setAgentView(!renderer.showAgentView); canvas.focus(); };
    $("btn-mute").onclick = function () {
      setMuted(!audio.toggle());
      canvas.focus();
    };
    $("btn-boss").onclick = function () { jumpToBoss(0); canvas.focus(); };
    $("btn-stage").onclick = function () { jumpToBoss(1); canvas.focus(); };
    Array.prototype.forEach.call(document.querySelectorAll("[data-speed]"), function (b) {
      b.onclick = function () { setSpeed(Number(b.getAttribute("data-speed"))); canvas.focus(); };
    });
  }

  function updatePanel() {
    var runs = state.runs;
    $("stat-runs").textContent = runs.length;
    $("stat-avg").textContent = runs.length
      ? Math.round(runs.reduce(function (s, r) { return s + r; }, 0) / runs.length) : "-";
    var o = state.overlay, on = state.autopilot && o && o.probs;
    $("joy-q").textContent = on ? Math.round(100 * o.probs[o.action]) + "%" : "--";
  }

  // ------------------------------------------------------------- 遊戲流程
  function newGame() {
    world.reset(Math.floor(Math.random() * 1e9));
    renderer.reset();
    state.scene = "playing";
    state.overTimer = 0;
    audio.start();
  }

  // demo 用的捷徑：跳過雜魚直接打魔王（也可以跳到下一關的魔王）。
  function jumpToBoss(extraStages) {
    if (state.scene !== "playing") newGame();
    world.stage = Math.min(world.stage + extraStages, R.FINAL_STAGE);
    world.enemies = world.enemies.filter(function (e) { return !e.isBoss; });
    world.director.state = S.Director.IDLE;
    world.stageFrame = R.BOSS_TIME - 1;
  }

  function stepOnce() {
    var dx, dy, focus, bomb = false;
    if (state.autopilot) {
      if (world.frame % FRAME_SKIP === 0) {
        F.observe(world, state.obs);
        var r = policy.act(state.obs);
        state.action = r.action;
        state.overlay = { obs: state.obs, probs: r.probs, action: r.action };
      }
      var a = F.ACTIONS[state.action];
      dx = a[0]; dy = a[1]; focus = a[2];
    } else {
      var k = state.keys;
      dx = (k.ArrowRight || k.KeyD ? 1 : 0) - (k.ArrowLeft || k.KeyA ? 1 : 0);
      dy = (k.ArrowDown || k.KeyS ? 1 : 0) - (k.ArrowUp || k.KeyW ? 1 : 0);
      focus = !!(k.ShiftLeft || k.ShiftRight);
      bomb = state.bomb;
      state.bomb = false;
      if (renderer.showAgentView && world.frame % FRAME_SKIP === 0) {
        state.overlay = { obs: F.observe(world, state.obs), probs: null, action: 0 };
      }
    }
    world.step(dx, dy, focus, bomb);
    audio.handle(world.events);
    renderer.handleEvents(world.events);
    if (world.done) {
      state.scene = "over";
      state.overTimer = 0;
      if (state.autopilot) state.runs.push(world.score);
      if (world.score > state.best) { state.best = world.score; writeBest(state.best); }
    }
  }

  function hud() {
    return { hiscore: state.best, autopilot: state.autopilot,
             action: state.autopilot ? state.action : null };
  }

  function drawTitle() {
    var ctx = renderer.ctx;
    renderer.draw(world, null, hud());
    ctx.fillStyle = "rgba(10,8,30,0.6)";
    ctx.fillRect(0, 0, R.WIDTH, R.HEIGHT);
    renderer.text("VERTICAL", 44, R.WIDTH / 2, 150, "#ffe65a", "center", "middle");
    renderer.text("SHMUP", 44, R.WIDTH / 2, 200, "#ffe65a", "center", "middle");
    renderer.text("ENTER  play", 18, R.WIDTH / 2, 300, "#fff", "center", "middle");
    renderer.text(policy ? "A  watch the PPO autopilot" : "(no model exported yet)", 16,
                  R.WIDTH / 2, 332, policy ? "#fff" : "#888", "center", "middle");
    var lines = ["ARROWS / WASD  move", "SHIFT  focus (slow)", "X  bomb",
                 "TAB  autopilot   V  agent view", "P  pause   M  mute"];
    lines.forEach(function (l, i) {
      renderer.text(l, 12, R.WIDTH / 2, 420 + i * 22, "#b4c8ff", "center", "middle");
    });
  }

  function draw() {
    if (state.scene === "title") { drawTitle(); return; }
    renderer.draw(world, state.overlay, hud());
    if (state.speed > 1) renderer.text("x" + state.speed, 12, R.WIDTH - 8, R.HEIGHT - 24, "#fff", "right");
    if (state.scene === "paused") {
      renderer.text("PAUSED", 34, R.WIDTH / 2, R.HEIGHT / 2, "#fff", "center", "middle");
    } else if (state.scene === "over") {
      renderer.text(world.cleared ? "ALL CLEAR!" : (world.player.hp > 0 ? "THE END" : "GAME OVER"), 38,
                    R.WIDTH / 2, R.HEIGHT / 2 - 40, world.cleared ? "#ffe65a" : "#ff5a5a", "center", "middle");
      renderer.text("SCORE " + world.score, 18, R.WIDTH / 2, R.HEIGHT / 2 + 10, "#fff", "center", "middle");
      renderer.text("ENTER  retry", 14, R.WIDTH / 2, R.HEIGHT / 2 + 80, "#fff", "center", "middle");
    }
  }

  // ------------------------------------------------------------- 鍵盤輸入
  window.addEventListener("keydown", function (e) {
    state.keys[e.code] = true;
    if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Space", "Tab"].indexOf(e.code) >= 0) {
      e.preventDefault();
    }
    audio.start();
    if (e.code === "Tab") {
      setAutopilot(!state.autopilot);
      if (state.autopilot && state.scene !== "playing") newGame();
    } else if (e.code === "KeyV") {
      setAgentView(!renderer.showAgentView);
    } else if (e.code === "KeyM") {
      setMuted(!audio.toggle());
    } else if (state.scene === "title" && (e.code === "Enter" || e.code === "Space")) {
      setAutopilot(false); newGame();
    } else if (state.scene === "title" && e.code === "KeyA" && policy) {
      setAutopilot(true); newGame();
    } else if (state.scene === "over" && (e.code === "Enter" || e.code === "Space")) {
      newGame();
    } else if (e.code === "KeyP" && (state.scene === "playing" || state.scene === "paused")) {
      state.scene = state.scene === "playing" ? "paused" : "playing";
    } else if (e.code === "KeyX" && state.scene === "playing") {
      state.bomb = true;
    }
  });
  window.addEventListener("keyup", function (e) { state.keys[e.code] = false; });
  window.addEventListener("blur", function () { state.keys = {}; });

  // ------------------------------------------------------------- 主迴圈
  var last = 0, acc = 0, panelTick = 0;
  function frame(now) {
    if (!last) last = now;
    acc += Math.min(now - last, 250);
    last = now;
    while (acc >= STEP_MS) {
      acc -= STEP_MS;
      if (state.scene === "playing") {
        for (var i = 0; i < state.speed && state.scene === "playing"; i++) stepOnce();
      } else if (state.scene === "over") {
        state.overTimer += 1;
        if (state.autopilot && state.overTimer > 2 * R.FPS) newGame();
      }
    }
    draw();
    if (++panelTick % 6 === 0) updatePanel();
    requestAnimationFrame(frame);
  }

  S.debug = { world: function () { return world; }, state: state };   // 方便在瀏覽器 console 除錯
  initPanel();
  setSpeed(1);
  renderer.load(function () { requestAnimationFrame(frame); });
})(this.Shmup = this.Shmup || {});
