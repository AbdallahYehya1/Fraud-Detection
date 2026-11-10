import numpy as np
import pandas as pd
import pytest

from fraudinv import data, evaluation as ev
from fraudinv.events import event_id


def segment_frame(n_per_step: dict[int, int], partition="validation") -> pd.DataFrame:
    rows = []
    r = 0
    for step, n in n_per_step.items():
        for _ in range(n):
            rows.append({"step": step, "partition": partition, "day": (step - 1) // 24,
                         "event_id": event_id("FIX", r)})
            r += 1
    df = pd.DataFrame(rows)
    df["tie_key"] = ev.tie_keys(df["event_id"])
    return df


def test_topk_takes_highest_scores_per_segment():
    df = segment_frame({s: 2 for s in range(25, 49)} | {s: 2 for s in range(49, 73)})  # days 1 and 2
    score = np.arange(len(df), dtype=float)
    sel = ev.select_daily_topk(df, score, k=3)
    for day, g in df.groupby("day"):
        chosen = score[g.index][sel.loc[g.index, "selected"].to_numpy()]
        assert sorted(chosen) == sorted(score[g.index])[-3:]
    assert sel["selected"].sum() == 6


def test_ties_broken_by_event_hash_not_labels():
    df = segment_frame({s: 3 for s in range(1, 25)})
    score = np.zeros(len(df))
    sel_a = ev.select_daily_topk(df, score, k=5)["selected"].to_numpy()
    # reorder the frame: same events selected
    shuffled = df.sample(frac=1.0, random_state=3)
    sel_b = ev.select_daily_topk(shuffled, score[shuffled.index], k=5)["selected"]
    assert set(df.loc[sel_a, "event_id"]) == set(shuffled.loc[sel_b.to_numpy(), "event_id"])
    expected = df.sort_values("tie_key").head(5)["event_id"]
    assert set(expected) == set(df.loc[sel_a, "event_id"])


def test_partial_segment_capacity_is_prorated():
    df = segment_frame({s: 10 for s in range(282, 289)})  # 7 observed hours of day 11
    sel = ev.select_daily_topk(df, np.random.default_rng(0).random(len(df)), k=100)
    assert sel["capacity"].iloc[0] == 29 and sel["segment_hours"].iloc[0] == 7
    assert sel["selected"].sum() == 29


def test_capacity_metrics_and_undefined_recall():
    m = ev.capacity_metrics(np.array([1, 0, 0, 1]), np.array([True, True, False, False]))
    assert m == {"alerts": 2, "true_positives": 1, "false_alerts": 1, "positives": 2, "legitimate": 2,
                 "precision": 0.5, "recall": 0.5, "false_alerts_per_1000_legitimate": 500.0}
    none = ev.capacity_metrics(np.zeros(3), np.array([True, False, False]))
    assert none["recall"] is None and none["precision"] == 0.0
    empty = ev.capacity_metrics(np.array([1, 0]), np.array([False, False]))
    assert empty["precision"] is None


def test_constant_score_ap_equals_prevalence():
    y = np.array([0] * 97 + [1] * 3)
    assert ev.ranking_metrics(y, np.zeros(100))["average_precision"] == pytest.approx(0.03)


def test_seeded_random_is_deterministic_and_seed_dependent():
    ids = pd.Series([event_id("FIX", i) for i in range(100)])
    a, b = ev.seeded_random_scores(ids, 1), ev.seeded_random_scores(ids, 1)
    assert np.array_equal(a, b) and not np.array_equal(a, ev.seeded_random_scores(ids, 2))
    assert ((a >= 0) & (a < 1)).all()


def test_hour_mix_is_evaluator_only_classification():
    df = pd.DataFrame({"step": [1, 1, 2, 2, 3]})
    kinds = ev.hour_label_mix(df, np.array([1, 1, 1, 0, 0]))
    assert kinds.tolist() == ["pure_positive", "pure_positive", "mixed", "mixed", "no_positive"]


def test_test_partition_is_sealed():
    with pytest.raises(data.TestAccessError):
        data.load_partition("test")
    with pytest.raises(data.TestAccessError):
        data.check_access("test", allow_test=False)
    if not data.FROZEN_SELECTION.exists():
        with pytest.raises(data.TestAccessError, match="frozen selection"):
            data.check_access("test", allow_test=True)
