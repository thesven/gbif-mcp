"""Verify distributable package membership without local state or cache files."""

from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
dist_dir = root / "dist"
archives = sorted(dist_dir.glob("gbif_mcp-0.2.0*"))
assert len(archives) == 2, f"Expected a wheel and a source archive, found: {archives}"

for path in archives:
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
        assert "gbif_mcp/__init__.py" in names, "Missing __init__.py in wheel"
        assert "gbif_mcp/server.py" in names, "Missing server.py in wheel"
        assert "gbif_mcp/client.py" in names, "Missing client.py in wheel"
    else:
        with tarfile.open(path) as archive:
            names = archive.getnames()
        assert any(n.endswith("/README.md") for n in names), "Missing README.md in sdist"
        assert any(n.endswith("/pyproject.toml") for n in names), "Missing pyproject.toml in sdist"

    for name in names:
        parts = Path(name).parts
        assert not {".venv", ".git", ".pytest_cache", ".ruff_cache", "__pycache__"} & set(parts), (
            f"Found forbidden directory in archive: {name}"
        )
        assert not any(p.startswith(".env") for p in parts), f"Found environment file in {name}"
        assert not name.endswith((".pyc", ".pyo", ".sqlite", ".db")), (
            f"Found unexpected binary or database file: {name}"
        )

    print(f"{path.name}: {len(names)} entries, clean package membership confirmed.")
