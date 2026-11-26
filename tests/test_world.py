from shmup.core import World
from shmup.core import rules as R
from shmup.core.entities import Bullet


def run(world, frames, immortal=True):
    """左右來回移動；回傳畫面上最多同時出現幾顆敵彈。"""
    most = 0
    for f in range(frames):
        world.step((f // 30) % 3 - 1, 0)
        most = max(most, len(world.bullets))
        if immortal:
            world.player.hp = R.PLAYER_MAX_HP
    return most


def test_same_seed_same_game():
    a, b = World(5), World(5)
    run(a, 1500)
    run(b, 1500)
    assert (a.score, len(a.bullets), a.player.x, a.rng.state) == \
           (b.score, len(b.bullets), b.player.x, b.rng.state)


def test_enemies_shoot_and_boss_arrives():
    w = World(1)
    most = run(w, R.BOSS_TIME + R.BOSS_WARNING_FRAMES + 5)
    assert w.boss is not None
    assert most > 20, "敵人應該要開火"


def test_bomb_clears_bullets_and_costs_one():
    w = World(2)
    w.bullets = [Bullet(100.0, 100.0, 0.0, 1.0) for _ in range(10)]
    bombs = w.player.bombs
    w.step(0, 0, bomb=True)
    assert w.bullets == []
    assert w.player.bombs == bombs - 1


def test_hit_spends_auto_bomb_then_hp():
    w = World(3)
    p = w.player
    p.bombs = 1
    w.bullets = [Bullet(p.x, p.y, 0.0, 0.0)]
    assert w.step() == 0 and p.bombs == 0          # 自動炸彈擋掉了
    p.invuln = 0
    w.bullets = [Bullet(p.x, p.y, 0.0, 0.0)]
    assert w.step() == 1 and p.hp == R.PLAYER_MAX_HP - 1


def test_shield_item_absorbs_a_hit():
    w = World(4)
    p = w.player
    p.shield, p.bombs = True, 0
    w.bullets = [Bullet(p.x, p.y, 0.0, 0.0)]
    assert w.step() == 0
    assert not p.shield and p.hp == R.PLAYER_MAX_HP


def test_game_over():
    w = World(6)
    p = w.player
    p.hp, p.bombs = 1, 0
    w.bullets = [Bullet(p.x, p.y, 0.0, 0.0)]
    w.step()
    assert w.done


def test_two_stages_then_all_clear():
    """第 1 關一隻魔王，第 2 關（最後一關）兩隻；兩隻都打倒就 ALL CLEAR。"""
    w = World(7)
    seen = []
    for stage in (1, 2):
        w.stage, w.stage_frame = stage, R.BOSS_TIME - 1
        for _ in range(R.BOSS_WARNING_FRAMES + 200):
            w.step()
            w.player.hp = R.PLAYER_MAX_HP
        bosses = [e for e in w.enemies if e.is_boss]
        seen.append(len(bosses))
        for b in bosses:
            w.damage_enemy(b, 10 ** 6)
        w.enemies = [e for e in w.enemies if e.alive]
    assert seen == [1, 2]
    assert w.done and w.cleared
