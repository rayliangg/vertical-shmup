// 用純 JavaScript 算 PPO 的策略網路（不需要任何機器學習函式庫）。
// 權重來自 web/model/ppo_model.js，由 scripts/export_web.py 從 Stable Baselines3 的模型匯出。
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
