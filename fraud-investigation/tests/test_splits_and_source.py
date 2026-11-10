import zipfile

import numpy as np
import pytest

from fraudinv import config, splits
from fraudinv.source import SourceMismatch, extract_csv, sha256, verify_file


def test_frozen_partitions_are_contiguous_whole_hours():
    bounds = splits.partitions()
    assert bounds == {"train": (1, 281), "validation": (282, 355), "test": (356, 743)}
    splits.validate_partitions(bounds, 1, 743)
    assert config.split_protocol()["status"] == "frozen"


def test_partition_validation_catches_gaps_and_overlaps():
    with pytest.raises(ValueError):
        splits.validate_partitions({"a": (1, 10), "b": (12, 20)}, 1, 20)
    with pytest.raises(ValueError):
        splits.validate_partitions({"a": (1, 10), "b": (10, 20)}, 1, 20)
    with pytest.raises(ValueError):
        splits.validate_partitions({"a": (1, 10), "b": (11, 19)}, 1, 20)


def test_assignment_and_day_convention():
    steps = np.array([1, 24, 25, 281, 282, 355, 356, 743])
    assert splits.assign_partition(steps).tolist() == [
        "train", "train", "train", "train", "validation", "validation", "test", "test"]
    assert splits.simulation_day(steps).tolist() == [0, 0, 1, 11, 11, 14, 14, 30]
    with pytest.raises(ValueError):
        splits.assign_partition(np.array([0]))
    with pytest.raises(ValueError):
        splits.assign_partition(np.array([744]))


def test_partial_segment_capacity():
    assert splits.segment_capacity(100, 24) == 100
    assert splits.segment_capacity(100, 7) == 29
    assert splits.segment_capacity(50, 5) == 10
    assert splits.segment_capacity(50, 6) == 13  # 12.5 rounds up
    assert splits.segment_capacity(1, 1) == 1


def test_contract_split_versions_linked():
    assert config.feature_contract()["split_protocol"] == config.split_protocol()["protocol_version"]
    assert config.split_protocol()["csv_sha256"] == config.data_source()["csv"]["sha256"]


def test_verify_and_safe_extract(tmp_path):
    payload = b"step,type\n1,PAYMENT\n"
    archive = tmp_path / "a.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("data.csv", payload)
        zf.writestr("../escape.csv", b"evil")
    target = tmp_path / "out" / "fixed.csv"
    extract_csv(archive, "data.csv", target)
    assert target.read_bytes() == payload
    assert not (tmp_path / "escape.csv").exists()
    good = verify_file(target, len(payload), sha256(target))
    assert good["verified"]
    with pytest.raises(SourceMismatch):
        verify_file(target, len(payload) + 1, sha256(target))
    with pytest.raises(SourceMismatch):
        verify_file(target, len(payload), "0" * 64)
    with pytest.raises(SourceMismatch):
        extract_csv(archive, "missing.csv", target)
