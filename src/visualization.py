"""
visualization.py — Charts for the valuation, saved as PNG files in outputs/.

Design rules used here (kept deliberately simple and consistent):
  - one colour per job: blue for the company's numbers, orange only to contrast a
    second category; text and axes in neutral greys, never in a series colour
  - actual vs forecast is shown by line style (solid vs dashed) AND a legend,
    so the difference never depends on colour alone
  - thin bars, light hairline gridlines, values labelled directly where useful
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")                     # draw to files only (no pop-up windows)
import matplotlib.pyplot as plt           # noqa: E402
import numpy as np                        # noqa: E402
import pandas as pd                       # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from src.model import CompanyInputs, ModelResults  # noqa: E402

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs"

# Colours (validated palette: blue and orange pass colour-blindness checks together)
BLUE = "#2a78d6"
ORANGE = "#eb6834"
INK = "#0b0b0b"          # titles and values
INK_2 = "#52514e"        # secondary text
MUTED = "#898781"        # axis labels and ticks
GRID = "#e1e0d9"         # hairline gridlines
AXIS = "#c3c2b7"         # baseline
SURFACE = "#fcfcfb"      # background
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 10,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": AXIS,
    "axes.labelcolor": MUTED,
    "axes.titlecolor": INK,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.axisbelow": True,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "legend.frameon": False,
    "legend.labelcolor": INK_2,
})


def _money_scale(values) -> tuple[float, str]:
    """Show large amounts in $ billions, smaller ones in $ millions."""
    return (1000.0, "$ billions") if max(abs(v) for v in values) >= 10_000 else (1.0, "$ millions")


def _save(fig, inputs: CompanyInputs, name: str) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    path = OUTPUT_DIR / f"{inputs.ticker}_{name}.png"
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return path


def history_vs_forecast_chart(inputs: CompanyInputs, history: pd.Series, forecast: pd.Series,
                              item_name: str, file_name: str) -> Path:
    """Line chart: actual years solid, forecast years dashed, joined at the last actual year."""
    divisor, unit = _money_scale(list(history) + list(forecast))
    fig, ax = plt.subplots(figsize=(8, 4.2))

    hist_years = [int(y) for y in history.index]
    fc_years = [hist_years[-1]] + [int(y) for y in forecast.index]       # join the two lines
    fc_values = [history.iloc[-1]] + list(forecast)

    ax.plot(hist_years, history / divisor, color=BLUE, linewidth=2, marker="o", markersize=6,
            label="Actual")
    ax.plot(fc_years, np.array(fc_values) / divisor, color=BLUE, linewidth=2, linestyle="--",
            marker="o", markersize=6, markerfacecolor=SURFACE, markevery=list(range(1, len(fc_years))),
            label="Forecast (your assumptions)")

    # Direct labels on the first actual, last actual and last forecast point only.
    for year, value in [(hist_years[0], history.iloc[0]), (hist_years[-1], history.iloc[-1]),
                        (fc_years[-1], fc_values[-1])]:
        ax.annotate(f"{value / divisor:,.0f}", (year, value / divisor), textcoords="offset points",
                    xytext=(0, 9), ha="center", color=INK, fontsize=9)

    ax.axvspan(hist_years[-1] + 0.5, fc_years[-1] + 0.5, color=GRID, alpha=0.35, linewidth=0)
    ax.set_title(f"{inputs.name}: {item_name}, actual vs forecast")
    ax.set_ylabel(unit)
    ax.set_xticks(hist_years + fc_years[1:])
    ax.set_xticklabels([f"FY{y % 100:02d}" + ("E" if y > hist_years[-1] else "")   # FY21 ... FY30E
                        for y in hist_years + fc_years[1:]])
    ax.set_ylim(0, max(max(history), max(fc_values)) / divisor * 1.15)          # room for labels
    ax.grid(axis="x", visible=False)
    ax.legend(loc="lower right")
    return _save(fig, inputs, file_name)


def ufcf_chart(inputs: CompanyInputs, results: ModelResults) -> Path:
    """Bars of forecast unlevered free cash flow, labelled with their values."""
    ufcf = results.ufcf.loc["ufcf"]
    divisor, unit = _money_scale(ufcf)
    fig, ax = plt.subplots(figsize=(8, 4.2))
    labels = [f"FY{int(y) % 100:02d}E" for y in ufcf.index]
    bars = ax.bar(labels, ufcf / divisor, width=0.45, color=BLUE)
    ax.bar_label(bars, labels=[f"{v / divisor:,.1f}" for v in ufcf], padding=3, color=INK, fontsize=9)
    ax.set_ylim(min(0, ufcf.min() / divisor * 1.15), max(0, ufcf.max() / divisor * 1.15))  # room for labels
    ax.axhline(0, color=AXIS, linewidth=1)
    ax.set_title(f"{inputs.name}: forecast unlevered free cash flow")
    ax.set_ylabel(unit)
    ax.grid(axis="x", visible=False)
    return _save(fig, inputs, "3_ufcf")


def ev_composition_chart(inputs: CompanyInputs, results: ModelResults) -> Path:
    """One stacked bar: how much of enterprise value comes from the forecast vs the terminal value."""
    v = results.valuation
    divisor, unit = _money_scale([v.enterprise_value])
    fig, ax = plt.subplots(figsize=(8, 2.6))
    parts = [("PV of 5-year forecast cash flows", v.pv_forecast_ufcf, BLUE),
             ("PV of terminal value", v.pv_terminal_value, ORANGE)]
    left = 0.0
    for label, value, colour in parts:
        ax.barh([0], [value / divisor], left=left, height=0.45, color=colour, label=label,
                edgecolor=SURFACE, linewidth=2)
        ax.text(left + value / divisor / 2, 0.27, f"{value / v.enterprise_value:.0%}",
                ha="center", va="bottom", color=INK, fontsize=10, fontweight="bold")
        left += value / divisor
    word = "billion" if divisor == 1000 else "million"
    ax.set_title(f"{inputs.name}: where the enterprise value comes from\n"
                 f"(enterprise value ${v.enterprise_value / divisor:,.0f} {word})")
    ax.set_xlabel(unit)
    ax.set_yticks([])
    ax.set_ylim(-0.35, 0.5)
    ax.grid(axis="y", visible=False)
    ax.spines["left"].set_visible(False)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.5), ncol=2)
    return _save(fig, inputs, "4_ev_composition")


def scenario_chart(inputs: CompanyInputs, results: ModelResults) -> Path:
    """Implied share price per scenario, with the current market price as a reference line."""
    names = [r.name for r in results.scenario_results]
    prices = [r.implied_share_price for r in results.scenario_results]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    bars = ax.bar(names, prices, width=0.45, color=BLUE)
    ax.bar_label(bars, labels=[f"${p:,.2f}" for p in prices], padding=3, color=INK, fontsize=10)
    ax.axhline(inputs.share_price, color=INK_2, linewidth=1.5, linestyle=(0, (4, 3)))
    ax.annotate(f"Market price ${inputs.share_price:,.2f} ({inputs.price_date})",
                (len(names) - 0.45, inputs.share_price), textcoords="offset points", xytext=(0, 5),
                ha="right", va="bottom", color=INK_2, fontsize=9)
    ax.set_title(f"{inputs.name}: implied share price by scenario")
    ax.set_ylabel("$ per share")
    ax.set_ylim(0, max(prices + [inputs.share_price]) * 1.15)
    ax.set_xlim(-0.6, len(names) - 0.4)
    ax.grid(axis="x", visible=False)
    return _save(fig, inputs, "5_scenarios")


def sensitivity_chart(inputs: CompanyInputs, results: ModelResults) -> Path:
    """Heatmap of implied share price: WACC (rows) vs terminal growth (columns)."""
    grid = results.grid_growth
    values = grid.to_numpy(dtype=float)
    cmap = LinearSegmentedColormap.from_list("blue_ramp", BLUE_RAMP)
    fig, ax = plt.subplots(figsize=(8, 5))
    image = ax.imshow(values, cmap=cmap, aspect="auto")

    middle_r, middle_c = values.shape[0] // 2, values.shape[1] // 2
    norm_values = image.norm(values)
    for r in range(values.shape[0]):
        for c in range(values.shape[1]):
            text_colour = "white" if norm_values[r, c] > 0.55 else INK
            label = "n/a" if np.isnan(values[r, c]) else f"${values[r, c]:,.0f}"
            weight = "bold" if (r, c) == (middle_r, middle_c) else "normal"
            ax.text(c, r, label, ha="center", va="center", color=text_colour, fontsize=9, fontweight=weight)
    ax.add_patch(plt.Rectangle((middle_c - 0.5, middle_r - 0.5), 1, 1, fill=False, edgecolor=INK, linewidth=2))

    ax.set_xticks(range(values.shape[1]), [f"{g:.1%}" for g in grid.columns])
    ax.set_yticks(range(values.shape[0]), [f"{w:.2%}" for w in grid.index])
    ax.set_xlabel("Terminal growth rate")
    ax.set_ylabel("WACC")
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title(f"{inputs.name}: implied share price, WACC vs terminal growth\n"
                 f"(base case outlined; market price ${inputs.share_price:,.2f})")
    return _save(fig, inputs, "6_sensitivity")


def save_all_charts(inputs: CompanyInputs, results: ModelResults) -> list[Path]:
    """Create every chart and return the file paths."""
    return [
        history_vs_forecast_chart(inputs, results.financials.loc["revenue"],
                                  results.forecast.loc["revenue"], "revenue", "1_revenue"),
        history_vs_forecast_chart(inputs, results.financials.loc["ebitda"],
                                  results.forecast.loc["ebitda"], "EBITDA", "2_ebitda"),
        ufcf_chart(inputs, results),
        ev_composition_chart(inputs, results),
        scenario_chart(inputs, results),
        sensitivity_chart(inputs, results),
    ]
