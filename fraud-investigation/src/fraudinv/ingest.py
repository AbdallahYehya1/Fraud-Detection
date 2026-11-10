"""Convert the verified CSV to a typed Parquet file with stable row positions.

The raw CSV is never modified. ``source_row`` is the 0-based data-row position
in the original file, assigned while streaming in file order (before any sort or
filter). Event IDs are derived from it; see ``fraudinv.events``.
"""
from __future__ import annotations

import time
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

SCHEMA = {
    "step": pa.int32(),
    "type": pa.string(),
    "amount": pa.float64(),
    "nameOrig": pa.string(),
    "oldbalanceOrg": pa.float64(),
    "newbalanceOrig": pa.float64(),
    "nameDest": pa.string(),
    "oldbalanceDest": pa.float64(),
    "newbalanceDest": pa.float64(),
    "isFraud": pa.int8(),
    "isFlaggedFraud": pa.int8(),
}


def csv_to_parquet(csv_path: Path, out_path: Path, expected_columns: list[str],
                   expected_rows: int | None = None) -> dict:
    started = time.perf_counter()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    partial = out_path.with_suffix(".parquet.partial")
    reader = pacsv.open_csv(
        csv_path,
        read_options=pacsv.ReadOptions(block_size=32 * 1024 * 1024),
        convert_options=pacsv.ConvertOptions(column_types=SCHEMA, strings_can_be_null=False),
    )
    names = reader.schema.names
    if names != expected_columns:
        raise ValueError(f"header {names} != expected {expected_columns}")
    rows = 0
    writer = None
    try:
        for batch in reader:
            table = pa.Table.from_batches([batch])
            ids = pa.array(range(rows, rows + table.num_rows), type=pa.int64())
            table = table.add_column(0, "source_row", ids)
            if writer is None:
                writer = pq.ParquetWriter(partial, table.schema, compression="zstd")
            writer.write_table(table, row_group_size=1_000_000)
            rows += table.num_rows
    finally:
        if writer is not None:
            writer.close()
    if expected_rows is not None and rows != expected_rows:
        partial.unlink(missing_ok=True)
        raise ValueError(f"read {rows} rows, expected {expected_rows}")
    partial.replace(out_path)
    return {"rows": rows, "parquet": str(out_path), "parquet_bytes": out_path.stat().st_size,
            "elapsed_seconds": round(time.perf_counter() - started, 2)}
