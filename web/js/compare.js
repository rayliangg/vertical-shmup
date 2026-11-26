// 四個 agent 同時比較：第 100 / 500 / 2000 / 5000 回合的模型，在同一個 seed（同一局）上一起玩。
// 模型清單來自 web/model/manifest.js（訓練時每到一個里程碑就會自動更新）。
(function (S) {
  "use strict";
  var R = S.RULES, F = S.Features;
  var FRAME_SKIP = 2;                       // 跟訓練時一樣，每 2 個 frame 決定一次
  var STEP_MS = 1000 / R.FPS;
  var WANTED = ["ep100", "ep500", "ep2000", "ep5000"];
  var $ = function (id) { return document.getElementById(id); };

  var list = S.MODEL_LIST || [];
  var entries = WANTED.map(function (id) {
    for (var i = 0; i < list.length; i++) if (list[i].id === id) return list[i];
    return { id: id, label: "第 " + id.replace("ep", "") + " 回合", missing: true };
  });

  var seed = 100000, speed = 1, running = true;
  var panels = entries.map(function (entry, i) {
    var box = document.createElement("div");
    box.className = "agent";
    box.innerHTML = '<div class="agent-head"><b>' + entry.label + '</b><span id="st' + i + '"></span></div>' +
                    '<canvas width="760" height="720"></canvas>' +
                    '<div class="agent-foot" id="ft' + i + '"></div>';
    $("grid").appendChild(box);
    var canvas = box.querySelector("canvas");
    return { entry: entry, canvas: canvas, renderer: new S.Renderer(canvas), world: new S.World(seed),
             policy: null, action: 0, obs: new Float64Array(F.OBS_DIM), end: "" };
  });

  function describe(p) {
    var ev = p.entry.eval;
    if (p.entry.missing) return "還沒練到這一回合（訓練到了會自動出現）";
    if (!p.policy) return "載入中…";
    return ev ? "訓練時測試：平均撐 " + Math.round(ev.seconds) + " 秒、平均第 " +
                Number(ev.stage).toFixed(1) + " 關、通關 " + ev.clears + "/" + ev.episodes : "";
  }

  function restart(newSeed) {
    seed = newSeed;
    $("seed").textContent = seed;
    panels.forEach(function (p) {
      p.world.reset(seed);
      p.renderer.reset();
      p.action = 0;
      p.end = "";
    });
  }

  function stepPanel(p) {
    var w = p.world;
    if (!p.policy || w.done) return;
    if (w.frame % FRAME_SKIP === 0) {
      F.observe(w, p.obs);
      p.action = p.policy.act(p.obs).action;
    }
    var a = F.ACTIONS[p.action];
    w.step(a[0], a[1], a[2], false);
    p.renderer.handleEvents(w.events);
    if (w.done) p.end = w.cleared ? "ALL CLEAR!" : (w.player.hp > 0 ? "THE END" : "GAME OVER");
  }

  function drawPanel(p, i) {
    var w = p.world;
    p.renderer.draw(w, null, { hiscore: 0, autopilot: !!p.policy, action: p.policy && !w.done ? p.action : null,
                               label: p.entry.label.replace("第 ", "EP ").replace(" 回合", "") });
    if (p.end) {
      p.renderer.text(p.end, 38, R.WIDTH / 2, R.HEIGHT / 2, w.cleared ? "#ffe65a" : "#ff5a5a", "center", "middle");
    }
    if (!p.policy) {
      p.renderer.text(p.entry.missing ? "NOT TRAINED YET" : "LOADING", 24, R.WIDTH / 2, R.HEIGHT / 2,
                      "#888", "center", "middle");
    }
    var secs = (w.frame / R.FPS).toFixed(1);
    $("st" + i).textContent = secs + " 秒 · " + w.score + " 分 · 第 " + w.stage + " 關" + (p.end ? " · " + p.end : "");
    $("ft" + i).textContent = describe(p);
  }

  // ---- 主迴圈：四局用同樣的時間一起前進 ----
  var last = 0, acc = 0;
  function frame(now) {
    if (!last) last = now;
    acc += Math.min(now - last, 250);
    last = now;
    while (acc >= STEP_MS) {
      acc -= STEP_MS;
      if (running) for (var k = 0; k < speed; k++) panels.forEach(stepPanel);
    }
    panels.forEach(drawPanel);
    requestAnimationFrame(frame);
  }

  // ---- 按鈕 ----
  $("btn-restart").onclick = function () { restart(seed); };
  $("btn-new").onclick = function () { restart(Math.floor(Math.random() * 1e9)); };
  $("btn-pause").onclick = function () {
    running = !running;
    $("btn-pause").textContent = running ? "暫停" : "繼續";
  };
  Array.prototype.forEach.call(document.querySelectorAll("[data-speed]"), function (b) {
    b.onclick = function () {
      speed = Number(b.getAttribute("data-speed"));
      Array.prototype.forEach.call(document.querySelectorAll("[data-speed]"), function (x) {
        x.classList.toggle("on", x === b);
      });
    };
  });

  // ---- 載入四個模型和圖片，然後開始 ----
  panels.forEach(function (p) {
    if (!p.entry.missing) S.loadModel(p.entry, function (policy) { p.policy = policy; });
  });
  var waiting = panels.length;
  restart(seed);
  panels.forEach(function (p) {
    p.renderer.load(function () { if (--waiting === 0) requestAnimationFrame(frame); });
  });
})(this.Shmup = this.Shmup || {});
