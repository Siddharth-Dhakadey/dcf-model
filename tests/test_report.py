"""Tests for the one-page summary."""

from src.company import load_company
from src.model import run_model
from src.report import save_summary, summary_lines


def maple_summary() -> list[str]:
    inputs = load_company("MAPLE")
    return summary_lines(inputs, run_model(inputs))


def test_summary_shows_the_headline_numbers():
    text = "\n".join(maple_summary())
    assert "DCF VALUATION" in text
    assert "Implied share price:      $52.74" in text
    assert "Current share price:      $30.00" in text
    for name, price in [("Bear", "$33.52"), ("Base", "$52.74"), ("Bull", "$67.39")]:
        assert f"{name} case:" in text and price in text


def test_summary_fits_on_a_normal_terminal():
    assert all(len(line) <= 80 for line in maple_summary())


def test_save_summary_writes_a_text_file(tmp_path):
    lines = maple_summary()
    path = save_summary(lines, tmp_path / "MAPLE_summary.txt")
    assert path.read_text(encoding="utf-8").splitlines() == lines
