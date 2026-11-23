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
