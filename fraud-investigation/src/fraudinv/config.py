"""Configuration loading and path resolution."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

APP_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = APP_ROOT / "config"
REPORTS_DIR = APP_ROOT / "reports"


@lru_cache(maxsize=None)
def load_yaml(name: str) -> dict:
    with (CONFIG_DIR / name).open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def data_source() -> dict:
    return load_yaml("data_source.yaml")


def split_protocol() -> dict:
    return load_yaml("split_protocol.yaml")


def feature_contract() -> dict:
    return load_yaml("feature_contract.yaml")


@dataclass(frozen=True)
class Paths:
    raw_archive: Path
    raw_csv: Path
    data_dir: Path

    @property
    def events_parquet(self) -> Path:
        return self.data_dir / "interim" / "paysim_v2_events.parquet"


def _resolve(env: str, default: str) -> Path:
    value = os.environ.get(env)
    path = Path(value) if value else APP_ROOT / default
    return path.resolve()


def paths() -> Paths:
    defaults = data_source()["default_paths"]
    return Paths(
        raw_archive=_resolve("FRAUDINV_RAW_ARCHIVE", defaults["raw_archive"]),
        raw_csv=_resolve("FRAUDINV_RAW_CSV", defaults["raw_csv"]),
        data_dir=_resolve("FRAUDINV_DATA_DIR", defaults["data_dir"]),
    )
