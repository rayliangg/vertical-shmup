import numpy as np

from shmup.agent.env import ShmupEnv, SyncVectorEnv
from shmup.agent.features import N_ACTIONS, OBS_DIM


def test_observation_shape_and_range():
    env = ShmupEnv(seed=1)
    obs = env.reset()
    assert obs.shape == (OBS_DIM,)
    for t in range(300):
        obs, reward, term, trunc, info = env.step(t % N_ACTIONS)
        assert np.all(np.isfinite(obs))
        assert np.abs(obs).max() < 50
        if term or trunc:
            obs = env.reset()


def test_vector_env_autoreset():
    venv = SyncVectorEnv(2, seed=0, max_steps=5)
    venv.reset()
    for _ in range(5):
        obs, rew, term, trunc, infos = venv.step(np.zeros(2, dtype=np.int64))
    assert trunc.all() and "final_obs" in infos[0]
    assert obs.shape == (2, OBS_DIM)
