import numpy as np

class Sampler:
    def __init__(self, name, params, seed=None):
        self.rng = np.random.default_rng(seed)
        if not hasattr(self.rng, name):
            raise AttributeError(f"NumPy Generator has no distribution: {name}")
        self._sampling_method = getattr(self.rng, name)
        self.dist_params = params

    def sample(self, size=None):
        # Squeeze arrays to scalars and force absolute values to prevent negative time steps
        val = self._sampling_method(**self.dist_params, size=size)
        return max(0.1, abs(float(np.squeeze(val))))