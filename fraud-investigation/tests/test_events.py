import pandas as pd
import pytest

from conftest import make_rows
from fraudinv import config
from fraudinv.events import attach_event_ids, event_id, event_prefix, tie_break_rank


@pytest.fixture
def prefix():
    src = config.data_source()
    return event_prefix(src["dataset_key"], src["csv"]["sha256"])


def test_prefix_format(prefix):
    assert prefix == "PS2-16910f90"
    assert event_id(prefix, 6_362_619) == "PS2-16910f90-6362619"
    assert event_id(prefix, 0) == "PS2-16910f90-0000000"


def test_identity_survives_sorting_and_filtering(history_fixture, prefix):
    tagged = attach_event_ids(history_fixture, prefix)
    original = tagged.set_index("event_id")
    reordered = tagged.sort_values(["amount", "nameDest"], ascending=False)
    filtered = reordered[reordered["type"].isin(["TRANSFER", "CASH_OUT"])].reset_index(drop=True)
    for _, row in filtered.iterrows():
        src = original.loc[row["event_id"]]
        assert src["source_row"] == row["source_row"]
        assert (src[["step", "type", "amount", "nameOrig", "nameDest"]] ==
                row[["step", "type", "amount", "nameOrig", "nameDest"]]).all()
        assert row["event_id"] == event_id(prefix, int(row["source_row"]))


def test_ids_unique_and_chunk_offsets_continue(history_fixture, prefix):
    first = attach_event_ids(history_fixture.iloc[:3], prefix, start_row=0)
    second = attach_event_ids(history_fixture.iloc[3:], prefix, start_row=3)
    whole = attach_event_ids(history_fixture, prefix)
    assert pd.concat([first, second])["event_id"].tolist() == whole["event_id"].tolist()
    assert whole["event_id"].is_unique


def test_reassignment_refused(history_fixture, prefix):
    tagged = attach_event_ids(history_fixture, prefix)
    with pytest.raises(ValueError):
        attach_event_ids(tagged, prefix)


def test_tie_break_is_label_independent(history_fixture, prefix):
    tagged = attach_event_ids(history_fixture, prefix)
    flipped = tagged.assign(isFraud=1 - tagged["isFraud"])
    assert tie_break_rank(tagged["event_id"]).tolist() == tie_break_rank(flipped["event_id"]).tolist()
    assert tie_break_rank(tagged["event_id"]).is_unique
