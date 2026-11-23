// xorshift32 亂數：完全對照 src/shmup/core/rng.py（同一個 seed 會產生同樣的亂數）。
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
