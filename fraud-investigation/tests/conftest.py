"""Shared synthetic fixtures. These are hand-made software fixtures, not PaySim rows."""
from __future__ import annotations

import pandas as pd
import pytest


def make_rows(rows: list[tuple]) -> pd.DataFrame:
    """rows: (step, type, amount, nameOrig, nameDest[, isFraud])"""
    cols = ["step", "type", "amount", "nameOrig", "nameDest", "isFraud"]
    padded = [r if len(r) == 6 else (*r, 0) for r in rows]
    return pd.DataFrame(padded, columns=cols)


@pytest.fixture
def history_fixture() -> pd.DataFrame:
    return make_rows([
        (1, "TRANSFER", 100.00, "C1", "C900"),
        (1, "TRANSFER", 50.25, "C2", "C900"),      # same step as above: not history for each other
        (2, "CASH_OUT", 10.10, "C3", "C900"),
        (2, "PAYMENT", 5.00, "C4", "M1"),
        (3, "CASH_OUT", 7.00, "C5", "C901"),
        (26, "TRANSFER", 1.00, "C6", "C900"),      # step 26: steps 2..25 are in window; step 1 is not
        (27, "TRANSFER", 2.00, "C7", "C900", 1),
        (30, "CASH_IN", 3.00, "C8", "C901"),
    ])
