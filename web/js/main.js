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
  var policy = S.loadPolicy();

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

  function initPanel() {
    if (policy) {
      var m = policy.meta || {};
      $("model-info").innerHTML = "PPO 模型練了 " +
        (m.step != null ? Number(m.step).toLocaleString() + " 步" : "?? 步") +
        (m.source ? "（" + m.source + "）" : "");
    } else {
      $("model-info").innerHTML = "還沒有模型，先訓練再跑<br><code>scripts/export_web.py</code>";
      $("btn-autopilot").disabled = true;
    }
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
