"""Exact-input, process-local caching for feature results."""

from __future__ import annotations

from math import isfinite

from quantforge.features.base import FeatureSpec, FeatureWindow

__all__ = ["FeatureCache"]

type _FeatureCacheKey = tuple[FeatureSpec, FeatureWindow]


class FeatureCache:
    """Store finite feature results by complete immutable computation inputs."""

    def __init__(self) -> None:
        self._values: dict[_FeatureCacheKey, float | None] = {}

    def put(
        self,
        spec: FeatureSpec,
        window: FeatureWindow,
        value: float | None,
    ) -> None:
        """Store an exact result, rejecting conflicting deterministic outputs."""
        key = _make_key(spec, window)
        _validate_value(value)

        if key in self._values:
            if self._values[key] == value:
                return
            raise ValueError("a different result is already cached for this exact key")

        self._values[key] = value

    def get(self, spec: FeatureSpec, window: FeatureWindow) -> float | None:
        """Return an exact cached result, including ``None``, or raise ``KeyError``."""
        return self._values[_make_key(spec, window)]

    def clear(self) -> None:
        """Remove all process-local cached results."""
        self._values.clear()

    def __len__(self) -> int:
        """Return the number of exact computation keys in the cache."""
        return len(self._values)


def _make_key(spec: FeatureSpec, window: FeatureWindow) -> _FeatureCacheKey:
    if not isinstance(spec, FeatureSpec):
        raise TypeError("spec must be a FeatureSpec")
    if not isinstance(window, FeatureWindow):
        raise TypeError("window must be a FeatureWindow")
    return (spec, window)


def _validate_value(value: float | None) -> None:
    if value is None:
        return
    if not isinstance(value, float):
        raise TypeError("value must be a float or None")
    if not isfinite(value):
        raise ValueError("value must be finite")
