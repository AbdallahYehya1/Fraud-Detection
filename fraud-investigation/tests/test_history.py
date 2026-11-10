import numpy as np
import pandas as pd
import pytest

from conftest import make_rows
from fraudinv.history import FEATURES, RecipientHistoryState, recipient_history


def by_step(df):
    return {s: g for s, g in df.groupby("step", sort=True)}


def incremental(df: pd.DataFrame) -> pd.DataFrame:
    state = RecipientHistoryState()
    parts = []
    for step, rows in by_step(df).items():
        parts.append(state.features(rows, step))
        state.update(rows.drop(columns=["isFraud"]), step)
    return pd.concat(parts).loc[df.index]


def test_expected_values(history_fixture):
    h = recipient_history(history_fixture)
    # step-1 rows to C900 do not see each other
    assert h.loc[[0, 1], "dest_prior_count"].tolist() == [0, 0]
    assert h.loc[[0, 1], "dest_has_prior"].tolist() == [0, 0]
    assert np.isnan(h.loc[0, "dest_steps_since_last"])
    # step 2 sees both step-1 rows, with exact cent sums
    assert h.loc[2, "dest_prior_count"] == 2
    assert h.loc[2, "dest_prior_amount_sum"] == 150.25
    assert h.loc[2, "dest_steps_since_last"] == 1
    # step 26: all-history = 3 rows; 24-step window [2, 25] holds only the step-2 row
    assert h.loc[5, "dest_prior_count"] == 3
    assert h.loc[5, "dest_prior_count_24h"] == 1
    assert h.loc[5, "dest_steps_since_last"] == 24
    # step 27 adds the step-26 row; its window [3, 26] has dropped the step-2 row
    assert h.loc[6, "dest_prior_count"] == 4
    assert h.loc[6, "dest_prior_count_24h"] == 1
    # merchant destination with no earlier record
    assert h.loc[3, "dest_has_prior"] == 0


def test_vectorized_and_incremental_agree(history_fixture):
    a = recipient_history(history_fixture)[FEATURES]
    b = incremental(history_fixture)[FEATURES]
    pd.testing.assert_frame_equal(a, b, check_dtype=False)


def test_future_record_cannot_alter_earlier_features(history_fixture):
    before = recipient_history(history_fixture)
    future = make_rows([(40, "TRANSFER", 999.0, "C99", "C900"), (31, "CASH_OUT", 1.0, "C98", "C901")])
    extended = pd.concat([history_fixture, future], ignore_index=True)
    after = recipient_history(extended).loc[history_fixture.index]
    pd.testing.assert_frame_equal(before, after)
    # and the injected rows themselves do see the earlier history
    tail = recipient_history(extended).iloc[-2:]
    assert tail["dest_prior_count"].tolist() == [5, 2]


def test_within_hour_reordering_cannot_create_history(history_fixture):
    base = recipient_history(history_fixture)
    rng = np.random.default_rng(7)
    for _ in range(20):
        shuffled = history_fixture.sample(frac=1.0, random_state=int(rng.integers(1e9)))
        # also reverse rows inside each hour explicitly
        shuffled = shuffled.sort_values("step", kind="stable")
        got = recipient_history(shuffled).loc[history_fixture.index]
        pd.testing.assert_frame_equal(base, got)
        pd.testing.assert_frame_equal(base, incremental(shuffled).loc[history_fixture.index],
                                      check_dtype=False)


def test_many_same_hour_rows_see_no_history():
    df = make_rows([(5, "TRANSFER", float(i), f"C{i}", "C777") for i in range(50)])
    h = recipient_history(df)
    assert (h["dest_prior_count"] == 0).all() and (h["dest_has_prior"] == 0).all()


def test_labels_never_enter_state():
    state = RecipientHistoryState()
    rows = make_rows([(1, "TRANSFER", 1.0, "C1", "C2", 1)])
    state.features(rows, 1)
    with pytest.raises(ValueError, match="labels"):
        state.update(rows, 1)


def test_state_refuses_to_score_an_applied_step():
    state = RecipientHistoryState()
    rows = make_rows([(1, "TRANSFER", 1.0, "C1", "C2")]).drop(columns=["isFraud"])
    state.update(rows, 1)
    with pytest.raises(ValueError):
        state.features(rows, 1)
    with pytest.raises(ValueError):
        state.update(rows, 1)


def test_label_values_do_not_change_features(history_fixture):
    flipped = history_fixture.assign(isFraud=1 - history_fixture["isFraud"])
    pd.testing.assert_frame_equal(recipient_history(history_fixture), recipient_history(flipped))
