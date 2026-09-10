"""In-memory registration for feature implementations."""

from __future__ import annotations

from quantforge.features.base import Feature, FeatureSpec

__all__ = ["FeatureRegistry"]


class FeatureRegistry:
    """Register feature implementations by stable feature name."""

    def __init__(self) -> None:
        self._registrations: dict[str, tuple[FeatureSpec, Feature]] = {}
        self._registered_object_ids: set[int] = set()

    def register(self, feature: Feature) -> None:
        """Register a feature without computing it or replacing an existing name."""
        spec = feature.spec
        if not isinstance(spec, FeatureSpec):
            raise TypeError("feature.spec must be a FeatureSpec")
        if id(feature) in self._registered_object_ids:
            raise ValueError("the same feature object is already registered")
        if spec.name in self._registrations:
            raise ValueError(f"feature name {spec.name!r} is already registered")

        self._registrations[spec.name] = (spec, feature)
        self._registered_object_ids.add(id(feature))

    def get(self, name: str) -> Feature:
        """Return the registered feature for an exact name or raise ``KeyError``."""
        return self._registrations[name][1]

    def list_specs(self) -> tuple[FeatureSpec, ...]:
        """Return immutable metadata snapshots in registration order."""
        return tuple(spec for spec, _feature in self._registrations.values())

    def __len__(self) -> int:
        """Return the number of registered feature implementations."""
        return len(self._registrations)
