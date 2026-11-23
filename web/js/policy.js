// 用純 JavaScript 算 Dueling Q 網路（不需要任何機器學習函式庫）。
// 權重來自 web/model/dqn_model.js，由 scripts/export_web.py 產生。
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
  }
  Linear.prototype.forward = function (x, relu) {
    var y = new Float32Array(this.nOut), w = this.w, n = this.nIn;
    for (var o = 0; o < this.nOut; o++) {
      var s = this.b[o], base = o * n;
      for (var i = 0; i < n; i++) s += w[base + i] * x[i];
      y[o] = relu && s < 0 ? 0 : s;
    }
    return y;
  };

  function Policy(model) {
    var L = model.layers;
    this.torso = L.torso.map(function (l) { return new Linear(l); });
    this.value = L.value.map(function (l) { return new Linear(l); });
    this.advantage = L.advantage.map(function (l) { return new Linear(l); });
    this.meta = model.meta || {};
    this.obsDim = model.obs_dim;
  }

  function run(layers, x) {
    for (var i = 0; i < layers.length; i++) x = layers[i].forward(x, i < layers.length - 1);
    return x;
  }

  Policy.prototype.qValues = function (obs) {
    var h = this.torso[0].forward(obs, true);        // 主幹的兩層都要過 ReLU
    h = this.torso[1].forward(h, true);
    var v = run(this.value, h)[0];
    var a = run(this.advantage, h), mean = 0, i;
    for (i = 0; i < a.length; i++) mean += a[i];
    mean /= a.length;
    var q = new Float32Array(a.length);
    for (i = 0; i < a.length; i++) q[i] = v + a[i] - mean;
    return q;
  };

  Policy.prototype.act = function (obs) {
    var q = this.qValues(obs), best = 0;
    for (var i = 1; i < q.length; i++) if (q[i] > q[best]) best = i;
    return { action: best, q: q };
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
