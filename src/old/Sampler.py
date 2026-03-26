import numpy as np


class Sampler:
    def __init__(self, name, params, seed=None):
        """
        dist_name: str (e.g., 'normal', 'poisson', 'gamma')
        dist_params: dict (e.g., {'loc': 0, 'scale': 1})
        """
        self.rng = np.random.default_rng(seed)
        # Validate that the method exists on the generator
        if not hasattr(self.rng, name):
            raise AttributeError(f"NumPy Generator has no distribution: {dist_name}")
            
        self._sampling_method = getattr(self.rng, name)
        self.dist_params = params

    def sample(self, size=None):
        """Returns a single sample by default, or an array if size is specified."""
        return self._sampling_method(**self.dist_params, size=size)

# Example Usage:

# from Sampler import * 
# config = {
#     "name": "gamma",
#     "params": {"shape": 2.0, "scale": 1.0}
# }

# my_sampler = Sampler(**config)
# print(my_sampler.sample()) # Single float

