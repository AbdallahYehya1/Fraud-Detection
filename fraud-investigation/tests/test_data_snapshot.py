"""Regression gates on the real Parquet. Skipped when the dataset has not been ingested."""
import duckdb
import pytest

from fraudinv import config, splits

pytestmark = pytest.mark.data
PARQUET = config.paths().events_parquet


@pytest.fixture(scope="module")
def con():
    if not PARQUET.exists():
        pytest.skip(f"no ingested data at {PARQUET}; run `python -m fraudinv ingest`")
    c = duckdb.connect()
    c.execute(f"CREATE VIEW ev AS SELECT * FROM read_parquet('{PARQUET.as_posix()}')")
    yield c
    c.close()


def test_partition_support_matches_frozen_protocol(con):
    expected = {"train": (3_820_599, 3_193), "validation": (1_293_285, 770), "test": (1_248_736, 4_250)}
    for name, (lo, hi) in splits.partitions().items():
        rows, pos = con.execute(
            f"SELECT count(*), sum(isFraud) FROM ev WHERE step BETWEEN {lo} AND {hi}").fetchone()
        assert (rows, pos) == expected[name]


def test_duckdb_feature_table_matches_reference_implementation(con, tmp_path):
    import pandas as pd

    from fraudinv import features
    from fraudinv.history import FEATURES, recipient_history

    out = features.build(tmp_path / "hist.parquet", max_step=30)
    got = pd.read_parquet(out["path"]).set_index("source_row").sort_index()
    sample = con.execute("SELECT source_row, step, nameDest, amount FROM ev WHERE step <= 30 "
                         "ORDER BY source_row").df()
    ref = recipient_history(sample).set_index(sample["source_row"])
    assert len(got) == len(ref) > 100_000
    pd.testing.assert_frame_equal(got[FEATURES], ref[FEATURES], check_dtype=False)


def test_source_rows_complete_and_unique(con):
    n, distinct, lo, hi = con.execute(
        "SELECT count(*), count(DISTINCT source_row), min(source_row), max(source_row) FROM ev").fetchone()
    assert n == distinct == config.data_source()["csv"]["rows"] and (lo, hi) == (0, n - 1)
