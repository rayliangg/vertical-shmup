// 在 Node 裡跑網頁版的模擬，給 tests/test_web_parity.py 用。
// 用法：node js_harness.js <web 資料夾> <seed> <frame 數> [model.js]
"use strict";
var fs = require("fs"), path = require("path"), vm = require("vm");
var web = process.argv[2], seed = Number(process.argv[3]), frames = Number(process.argv[4]);
var modelFile = process.argv[5];

global.atob = function (s) { return Buffer.from(s, "base64").toString("binary"); };
["js/rules.js", "js/core.js"].forEach(function (f) {
  vm.runInThisContext(fs.readFileSync(path.join(web, f), "utf8"), { filename: f });
});
if (modelFile) vm.runInThisContext(fs.readFileSync(modelFile, "utf8"), { filename: "model.js" });
vm.runInThisContext(fs.readFileSync(path.join(web, "js/agent.js"), "utf8"), { filename: "agent.js" });
var S = global.Shmup, F = S.Features;
var world = new S.World(seed), trace = [];
var policy = modelFile ? S.policyFromData(S.MODELS_DATA[Object.keys(S.MODELS_DATA)[0]]) : null;

for (var f = 0; f < frames; f++) {
  var a = F.ACTIONS[Math.floor(f * 7 / 13) % F.ACTIONS.length];
  world.step(a[0], a[1], a[2], f % 997 === 500);
  world.player.hp = 5;                         // 讓它不會死，後面的關卡才測得到
  if (f % 25 === 0) {
    var obs = Array.prototype.slice.call(F.observe(world));
    var row = { frame: world.frame, score: world.score, stage: world.stage,
                bullets: world.bullets.length, enemies: world.enemies.length,
                items: world.items.length, x: world.player.x, y: world.player.y,
                state: world.rng.state, obs: obs };
    if (policy) row.probs = Array.prototype.slice.call(policy.act(obs).probs);
    trace.push(row);
  }
}
process.stdout.write(JSON.stringify(trace));
