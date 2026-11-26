import numpy as np

from shmup.rl.env import ShmupEnv
from shmup.rl.features import N_ACTIONS, OBS_DIM


def test_env_passes_sb3_checker():
    from stable_baselines3.common.env_checker import check_env
    check_env(ShmupEnv(), warn=True)


def test_observation_shape_and_range():
    env = ShmupEnv()
    env.seed(1)
    obs = env.reset()
    assert obs.shape == (OBS_DIM,)
    for t in range(300):
        obs, reward, done, info = env.step(t % N_ACTIONS)
        assert np.all(np.isfinite(obs))
        assert np.abs(obs).max() < 50
        if done:
            obs = env.reset()


def test_same_seed_same_episode():
    a, b = ShmupEnv(), ShmupEnv()
    oa, ob = a.reset_to(7), b.reset_to(7)
    for t in range(200):
        oa, ra, _, _ = a.step(t % N_ACTIONS)
        ob, rb, _, _ = b.step(t % N_ACTIONS)
    assert np.array_equal(oa, ob) and ra == rb


def test_time_limit_is_marked_as_truncated():
    env = ShmupEnv(max_steps=5)
    env.reset_to(0)
    for _ in range(5):
        _, _, done, info = env.step(0)
    assert done and info.get("TimeLimit.truncated")


def test_report_baselines_run():
    from shmup.rl.evaluate import evaluate, random_actor, still_actor
    for actor in (still_actor(), random_actor()):
        stats = evaluate(actor, episodes=1, max_steps=200)
        assert stats["episodes"] == 1 and stats["survival"] > 0
