"""Verify canonical source files and extract the CSV safely."""
from __future__ import annotations

import hashlib
import shutil
import zipfile
from pathlib import Path


class SourceMismatch(RuntimeError):
    pass


def sha256(path: Path, block: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(block), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_file(path: Path, expected_bytes: int, expected_sha256: str) -> dict:
    """Check size first (cheap), then SHA-256. Raises SourceMismatch on any difference."""
    if not path.exists():
        raise SourceMismatch(f"missing: {path}")
    size = path.stat().st_size
    if size != expected_bytes:
        raise SourceMismatch(f"{path}: {size} bytes, expected {expected_bytes}")
    digest = sha256(path)
    if digest != expected_sha256:
        raise SourceMismatch(f"{path}: sha256 {digest}, expected {expected_sha256}")
    return {"path": str(path), "bytes": size, "sha256": digest, "verified": True}


def extract_csv(archive: Path, member: str, target: Path) -> Path:
    """Extract one named CSV member to a fixed target path.

    Only the expected member name is read; archive paths are never used to build
    the output location, so a crafted entry cannot write outside ``target``.
    """
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
        if member not in names:
            raise SourceMismatch(f"{archive} lacks {member}; has {names}")
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix(target.suffix + ".partial")
        with zf.open(member) as src, partial.open("wb") as dst:
            shutil.copyfileobj(src, dst, length=8 * 1024 * 1024)
        partial.replace(target)
    return target
