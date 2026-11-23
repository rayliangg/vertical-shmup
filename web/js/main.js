// Browser entry point: fixed-timestep loop, input, scenes and the demo panel.
(function (S) {
  "use strict";
  var R = S.RULES, F = S.Features;
  var FRAME_SKIP = 2;                        // agent decides every 2 frames, like training
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

  // ------------------------------------------------------------- persistence
  function readBest() {
    try { return parseInt(localStorage.getItem("shmup.best") || "0", 10) || 0; }
    catch (e) { return 0; }
  }
  function writeBest(v) {
    try { localStorage.setItem("shmup.best", String(v)); } catch (e) { /* private mode */ }
  }

  // ------------------------------------------------------------- UI panel
  var $ = function (id) { return document.getElementById(id); };
  function setAutopilot(on) {
    state.autopilot = !!(on && policy);
    $("btn-autopilot").classList.toggle("on", state.autopilot);
    $("btn-autopilot").textContent = state.autopilot ? "Autopilot: ON" : "Autopilot: OFF";
  }
  function setSpeed(v) {
    state.speed = v;
    Array.prototype.forEach.call(document.querySelectorAll("[data-speed]"), function (b) {
      b.classList.toggle("on", Number(b.getAttribute("data-speed")) === v);
    });
  }
  function setAgentView(on) {
    renderer.showAgentView = on;
    $("btn-view").classList.toggle("on", on);
  }

  function initPanel() {
    if (policy) {
      var m = policy.meta || {}, ev = m.eval || {};
      $("model-info").innerHTML =
        "Dueling Double DQN &middot; " + S.MODEL.hidden + " hidden units<br>" +
        (m.step ? "trained " + Number(m.step).toLocaleString() + " decisions<br>" : "") +
        (ev.survival ? "eval survival " + Math.round(ev.survival / 30) + " s, stage " +
         Number(ev.stage).toFixed(1) : "");
    } else {
      $("model-info").innerHTML = "No model found.<br>Train, then run<br>" +
        "<code>python scripts/export_web.py</code>";
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
      $("btn-mute").textContent = audio.toggle() ? "Sound: ON" : "Sound: OFF";
      canvas.focus();
    };
    Array.prototype.forEach.call(document.querySelectorAll("[data-speed]"), function (b) {
      b.onclick = function () { setSpeed(Number(b.getAttribute("data-speed"))); canvas.focus(); };
    });
    var bars = $("q-bars");
    F.ACTIONS.forEach(function (a, i) {
      var row = document.createElement("div");
      row.className = "q-row";
      row.innerHTML = '<span class="q-label">' + actionLabel(a) + '</span><span class="q-bar" id="q' +
        i + '"></span>';
      bars.appendChild(row);
    });
  }

  function actionLabel(a) {
    var arrows = { "0,0": "·", "-1,0": "←", "1,0": "→", "0,-1": "↑", "0,1": "↓",
                   "-1,-1": "↖", "1,-1": "↗", "-1,1": "↙", "1,1": "↘" };
    return arrows[a[0] + "," + a[1]] + (a[2] ? " slow" : "");
  }

  function updatePanel() {
    $("stat-score").textContent = world.score;
    $("stat-stage").textContent = world.stage;
    $("stat-best").textContent = state.best;
    var runs = state.runs;
    $("stat-runs").textContent = runs.length;
    $("stat-avg").textContent = runs.length
      ? Math.round(runs.reduce(function (s, r) { return s + r; }, 0) / runs.length) : "-";
    var o = state.overlay;
    if (o && o.q) {
      var lo = Infinity, hi = -Infinity, i;
      for (i = 0; i < o.q.length; i++) { lo = Math.min(lo, o.q[i]); hi = Math.max(hi, o.q[i]); }
      for (i = 0; i < o.q.length; i++) {
        var bar = $("q" + i);
        bar.style.width = (8 + 92 * (o.q[i] - lo) / Math.max(hi - lo, 1e-6)) + "%";
        bar.classList.toggle("best", i === o.action);
      }
    }
  }

  // ------------------------------------------------------------- game flow
  function newGame() {
    world.reset(Math.floor(Math.random() * 1e9));
    renderer.reset();
    state.scene = "playing";
    state.overTimer = 0;
    audio.start();
  }

  function stepOnce() {
    var dx, dy, focus, bomb = false;
    if (state.autopilot) {
      if (world.frame % FRAME_SKIP === 0) {
        F.observe(world, state.obs);
        var r = policy.act(state.obs);
        state.action = r.action;
        state.overlay = { obs: state.obs, q: r.q, action: r.action };
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
        state.overlay = { obs: F.observe(world, state.obs), q: null, action: 0 };
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

  function drawTitle() {
    var ctx = renderer.ctx;
    renderer.draw(world, null);
    ctx.fillStyle = "rgba(10,8,30,0.6)";
    ctx.fillRect(0, 0, R.WIDTH, R.HEIGHT);
    renderer.text("VERTICAL", 44, R.WIDTH / 2, 150, "#ffe65a", "center", "middle");
    renderer.text("SHMUP", 44, R.WIDTH / 2, 200, "#ffe65a", "center", "middle");
    renderer.text("ENTER  play", 18, R.WIDTH / 2, 300, "#fff", "center", "middle");
    renderer.text(policy ? "A  watch the DQN autopilot" : "(no model exported yet)", 16,
                  R.WIDTH / 2, 332, policy ? "#fff" : "#888", "center", "middle");
    var lines = ["ARROWS / WASD  move", "SHIFT  focus (slow)", "X  bomb",
                 "TAB  autopilot   V  agent view", "P  pause   M  mute"];
    lines.forEach(function (l, i) {
      renderer.text(l, 12, R.WIDTH / 2, 420 + i * 22, "#b4c8ff", "center", "middle");
    });
  }

  function draw() {
    if (state.scene === "title") { drawTitle(); return; }
    renderer.draw(world, state.overlay);
    if (state.autopilot) renderer.text("AUTOPILOT (DQN)", 12, R.WIDTH / 2, R.HEIGHT - 24, "#50ff78");
    if (state.speed > 1) renderer.text("x" + state.speed, 12, R.WIDTH - 8, R.HEIGHT - 24, "#fff", "right");
    if (state.scene === "paused") {
      renderer.text("PAUSED", 34, R.WIDTH / 2, R.HEIGHT / 2, "#fff", "center", "middle");
    } else if (state.scene === "over") {
      renderer.text("GAME OVER", 38, R.WIDTH / 2, R.HEIGHT / 2 - 40, "#ff5a5a", "center", "middle");
      renderer.text("SCORE " + world.score, 18, R.WIDTH / 2, R.HEIGHT / 2 + 10, "#fff", "center", "middle");
      renderer.text("ENTER  retry", 14, R.WIDTH / 2, R.HEIGHT / 2 + 80, "#fff", "center", "middle");
    }
  }

  // ------------------------------------------------------------- input
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
      $("btn-mute").textContent = audio.toggle() ? "Sound: ON" : "Sound: OFF";
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

  // ------------------------------------------------------------- loop
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

  initPanel();
  setSpeed(1);
  renderer.load(function () { requestAnimationFrame(frame); });
})(this.Shmup = this.Shmup || {});
