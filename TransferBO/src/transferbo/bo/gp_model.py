"""Surrogate GP wrappers (sklearn default; BoTorch optional)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class PredictResult:
    mean: np.ndarray
    std: np.ndarray


class SurrogateGP:
    """Discrete-candidate GP surrogate.

    backend='sklearn' — fast baseline for discrete HTE lookup loops
    backend='botorch' — ExactGP + constant mean (optional path)
    """

    def __init__(
        self,
        *,
        backend: str = "sklearn",
        normalize_y: bool = True,
        random_state: int = 0,
    ) -> None:
        self.backend = backend.lower()
        self.normalize_y = normalize_y
        self.random_state = random_state
        self._model = None
        self._y_mean = 0.0
        self._y_std = 1.0

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        *,
        alpha: float | np.ndarray | None = None,
    ) -> "SurrogateGP":
        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64).reshape(-1)
        if self.normalize_y:
            self._y_mean = float(np.mean(y))
            self._y_std = float(np.std(y)) or 1.0
            y_fit = (y - self._y_mean) / self._y_std
        else:
            self._y_mean, self._y_std = 0.0, 1.0
            y_fit = y

        if self.backend == "sklearn":
            self._fit_sklearn(X, y_fit, alpha=alpha)
        elif self.backend == "botorch":
            if alpha is not None and not np.isscalar(alpha):
                raise ValueError("botorch backend does not support per-point alpha yet")
            self._fit_botorch(X, y_fit)
        else:
            raise ValueError(f"Unknown backend: {self.backend}")
        return self

    def predict(self, X: np.ndarray) -> PredictResult:
        X = np.asarray(X, dtype=np.float64)
        if self._model is None:
            raise RuntimeError("SurrogateGP must be fit before predict")
        if self.backend == "sklearn":
            mean, std = self._predict_sklearn(X)
        else:
            mean, std = self._predict_botorch(X)
        mean = mean * self._y_std + self._y_mean
        std = std * self._y_std
        return PredictResult(mean=mean, std=np.maximum(std, 1e-9))

    def _fit_sklearn(
        self,
        X: np.ndarray,
        y: np.ndarray,
        *,
        alpha: float | np.ndarray | None = None,
    ) -> None:
        from sklearn.gaussian_process import GaussianProcessRegressor
        from sklearn.gaussian_process.kernels import ConstantKernel, Matern, WhiteKernel

        # High-dim fingerprints: isotropic length-scale is more stable
        kernel = ConstantKernel(1.0, (1e-3, 1e3)) * Matern(
            length_scale=1.0, length_scale_bounds=(1e-2, 1e3), nu=2.5
        ) + WhiteKernel(noise_level=0.1, noise_level_bounds=(1e-5, 1e1))
        if alpha is None:
            alpha_fit: float | np.ndarray = 1e-4
        else:
            alpha_fit = np.asarray(alpha, dtype=np.float64)
            if alpha_fit.ndim == 0:
                alpha_fit = float(alpha_fit)
            elif alpha_fit.shape != (len(y),):
                raise ValueError(
                    f"alpha shape {alpha_fit.shape} must be () or ({len(y)},)"
                )
        self._model = GaussianProcessRegressor(
            kernel=kernel,
            normalize_y=False,
            n_restarts_optimizer=1,
            random_state=self.random_state,
            alpha=alpha_fit,
        )
        self._model.fit(X, y)

    def _predict_sklearn(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        mean, std = self._model.predict(X, return_std=True)
        return np.asarray(mean, dtype=np.float64), np.asarray(std, dtype=np.float64)

    def _fit_botorch(self, X: np.ndarray, y: np.ndarray) -> None:
        import torch
        from botorch.models import SingleTaskGP
        from botorch.fit import fit_gpytorch_mll
        from gpytorch.mlls import ExactMarginalLogLikelihood

        train_X = torch.tensor(X, dtype=torch.double)
        train_Y = torch.tensor(y, dtype=torch.double).unsqueeze(-1)
        model = SingleTaskGP(train_X, train_Y)
        mll = ExactMarginalLogLikelihood(model.likelihood, model)
        fit_gpytorch_mll(mll)
        self._model = model
        self._torch = torch

    def _predict_botorch(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        torch = self._torch
        model = self._model
        model.eval()
        with torch.no_grad():
            post = model.posterior(torch.tensor(X, dtype=torch.double))
            mean = post.mean.squeeze(-1).cpu().numpy()
            var = post.variance.squeeze(-1).cpu().numpy()
        return mean, np.sqrt(np.maximum(var, 1e-12))
