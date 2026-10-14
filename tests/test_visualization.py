"""Tests for the charts: every chart file is created and is a real PNG image."""

from src.company import load_company
from src.model import run_model
import src.visualization as viz


def test_save_all_charts_creates_six_png_files(tmp_path, monkeypatch):
    # Write into a temporary folder so the test never touches your real outputs/ folder.
    monkeypatch.setattr(viz, "OUTPUT_DIR", tmp_path)
    inputs = load_company("MAPLE")
    results = run_model(inputs)

    paths = viz.save_all_charts(inputs, results)

    assert len(paths) == 6
    for path in paths:
        assert path.exists()
        assert path.parent == tmp_path
        assert path.name.startswith("MAPLE_")
        assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"   # every PNG file starts with these bytes
        assert path.stat().st_size > 10_000                    # not an empty image
