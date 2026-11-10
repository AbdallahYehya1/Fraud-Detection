"""Feature-contract enforcement.

Every model feature set passes through ``validate_feature_set`` before fitting
or serving. A feature is rejected when its name matches a forbidden pattern,
when it is not declared in the contract, or when any declared input is a
forbidden source field (catches balance-derived features under neutral names).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from . import config


class ForbiddenFeatureError(ValueError):
    pass


@dataclass(frozen=True)
class FeatureContract:
    version: str
    forbidden_inputs: frozenset[str]
    forbidden_patterns: tuple[str, ...]
    features: Mapping[str, dict]
    transaction_types: tuple[str, ...]

    @classmethod
    def load(cls) -> "FeatureContract":
        raw = config.feature_contract()
        return cls(
            version=raw["contract_version"],
            forbidden_inputs=frozenset(f.lower() for f in raw["forbidden_inputs"]),
            forbidden_patterns=tuple(p.lower() for p in raw["forbidden_name_patterns"]),
            features=raw["features"],
            transaction_types=tuple(raw["transaction_types"]),
        )

    def check_inputs(self, name: str, inputs: Iterable[str]) -> None:
        bad = sorted(i for i in inputs if i.lower() in self.forbidden_inputs)
        if bad:
            raise ForbiddenFeatureError(f"{name}: forbidden inputs {bad}")

    def check_name(self, name: str) -> None:
        lowered = name.lower()
        hits = [p for p in self.forbidden_patterns if p in lowered]
        if hits:
            raise ForbiddenFeatureError(f"{name}: matches forbidden pattern {hits}")

    def validate_feature_set(
        self,
        names: Iterable[str],
        allow_ablation: bool = False,
        extra_specs: Mapping[str, dict] | None = None,
    ) -> list[str]:
        """Validate a list of feature names; returns them unchanged on success.

        ``extra_specs`` lets a caller propose an undeclared feature with its
        lineage; it is still checked against forbidden inputs and then rejected
        as undeclared, so proposals must be added to the contract file first.
        """
        names = list(names)
        if len(set(names)) != len(names):
            raise ForbiddenFeatureError(f"duplicate feature names: {names}")
        for name in names:
            self.check_name(name)
            if extra_specs and name in extra_specs:
                self.check_inputs(name, extra_specs[name].get("inputs", []))
            spec = self.features.get(name)
            if spec is None:
                raise ForbiddenFeatureError(f"{name}: not declared in contract {self.version}")
            self.check_inputs(name, spec.get("inputs", []))
            if spec.get("status") == "ablation_only" and not allow_ablation:
                raise ForbiddenFeatureError(f"{name}: ablation-only feature in a primary feature set")
        return names

    def check_frame_columns(self, columns: Iterable[str], allow_ablation: bool = False) -> None:
        """Reject a model matrix whose columns are raw forbidden fields or undeclared."""
        cols = list(columns)
        raw_hits = sorted(c for c in cols if c.lower() in self.forbidden_inputs)
        if raw_hits:
            raise ForbiddenFeatureError(f"model matrix contains forbidden fields {raw_hits}")
        base = []
        for c in cols:
            # one-hot columns are named type_onehot=<TYPE>
            base.append(c.split("=", 1)[0])
        self.validate_feature_set(dict.fromkeys(base), allow_ablation=allow_ablation)
