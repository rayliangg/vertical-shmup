import numpy as np

from shmup.agent.env import ShmupEnv
from shmup.agent.features import N_ACTIONS, OBS_DIM


def test_env_passes_sb3_checker():
    from stable_baselines3.common.env_checker import check_env
    check_env(ShmupEnv(), warn=True)


def test_observation_shape_and_range():
    env = ShmupEnv()
    obs, _ = env.reset(seed=1)
    assert obs.shape == (OBS_DIM,)
    for t in range(300):
        obs, reward, term, trunc, info = env.step(t % N_ACTIONS)
        assert np.all(np.isfinite(obs))
        assert np.abs(obs).max() < 50
        if term or trunc:
            obs, _ = env.reset()


def test_same_seed_same_episode():
    a, b = ShmupEnv(), ShmupEnv()
    oa, _ = a.reset(seed=7)
    ob, _ = b.reset(seed=7)
    for t in range(200):
        oa, ra, *_ = a.step(t % N_ACTIONS)
        ob, rb, *_ = b.step(t % N_ACTIONS)
    assert np.array_equal(oa, ob) and ra == rb


def test_truncates_at_max_steps():
    env = ShmupEnv(max_steps=5)
    env.reset(seed=0)
    for _ in range(5):
        _, _, term, trunc, _ = env.step(0)
    assert trunc and not term
