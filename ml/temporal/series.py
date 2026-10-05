"""Turn timestamped events into regular time series for lag/Granger tests.

numpy only (pandas is not a project dependency). Timestamps are converted to
hours since the epoch; the caller picks the bin width. Resolution is limited
by the data: YouTube and Reddit timestamps are to the second, Instagram post
dates are day-level only (decoded from the post shortcode), so Instagram
series must use bin_hours >= 24.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np


def to_epoch_hours(timestamps: list[datetime]) -> np.ndarray:
    return np.array([t.timestamp() / 3600.0 for t in timestamps], dtype=float)


def _bin_index(hours: np.ndarray, start: float, end: float, bin_hours: float) -> tuple[np.ndarray, np.ndarray, int]:
    n_bins = int(np.ceil((end - start) / bin_hours))
    idx = np.floor((hours - start) / bin_hours).astype(int)
    keep = (idx >= 0) & (idx < n_bins)
    return idx, keep, n_bins


def bin_counts(hours: np.ndarray, start: float, end: float, bin_hours: float) -> np.ndarray:
    """Number of events per bin over [start, end)."""
    idx, keep, n_bins = _bin_index(np.asarray(hours, dtype=float), start, end, bin_hours)
    return np.bincount(idx[keep], minlength=n_bins).astype(float)


def bin_mean(hours: np.ndarray, values: np.ndarray, start: float, end: float, bin_hours: float) -> np.ndarray:
    """Mean of `values` per bin; NaN for empty bins."""
    hours = np.asarray(hours, dtype=float)
    values = np.asarray(values, dtype=float)
    idx, keep, n_bins = _bin_index(hours, start, end, bin_hours)
    sums = np.bincount(idx[keep], weights=values[keep], minlength=n_bins)
    counts = np.bincount(idx[keep], minlength=n_bins)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(counts > 0, sums / counts, np.nan)
