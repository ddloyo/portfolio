"""
XIA Insights x Analytics — shared visual style for the portfolio.

Palette source: validated categorical/status palette (dataviz skill,
references/palette.md). Reused as-is across every project so the whole
portfolio reads as one coherent design system, the same way a real XIA
engagement would ship consistent-looking deliverables to a client.

Import this from any project's analysis.py to get matplotlib styling,
or import COLORS/STATUS from dashboard.py-generating scripts.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# ---- Categorical palette (fixed order — never re-cycled) -----------------
CATEGORICAL = [
    "#2a78d6",  # 1 blue
    "#eb6834",  # 2 orange
    "#1baf7a",  # 3 aqua
    "#eda100",  # 4 yellow
    "#e87ba4",  # 5 magenta
    "#008300",  # 6 green
    "#4a3aa7",  # 7 violet
    "#e34948",  # 8 red
]

STATUS = {
    "good": "#0ca30c",
    "warning": "#fab219",
    "serious": "#ec835a",
    "critical": "#d03b3b",
}

SEQUENTIAL_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#2a78d6", "#1c5cab", "#104281"]

INK = {
    "surface": "#fcfcfb",
    "page": "#f9f9f7",
    "primary": "#0b0b0b",
    "secondary": "#52514e",
    "muted": "#898781",
    "grid": "#e1e0d9",
    "axis": "#c3c2b7",
}

FONT_STACK = ["DejaVu Sans", "sans-serif"]


def apply_style():
    """Apply the XIA chart style to matplotlib for the current process."""
    plt.rcParams.update({
        "font.family": FONT_STACK,
        "figure.facecolor": INK["surface"],
        "axes.facecolor": INK["surface"],
        "axes.edgecolor": INK["axis"],
        "axes.labelcolor": INK["secondary"],
        "axes.titlecolor": INK["primary"],
        "axes.grid": True,
        "grid.color": INK["grid"],
        "grid.linewidth": 0.8,
        "text.color": INK["primary"],
        "xtick.color": INK["muted"],
        "ytick.color": INK["muted"],
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.prop_cycle": plt.cycler(color=CATEGORICAL),
        "savefig.facecolor": INK["surface"],
        "savefig.dpi": 160,
        "figure.figsize": (9, 5),
    })


def color(i):
    """Fixed categorical color by slot index (0-based), never re-cycled."""
    return CATEGORICAL[i % len(CATEGORICAL)]
