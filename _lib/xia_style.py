"""
XIA Insights x Analytics — shared visual style for the portfolio.

Palette: the XIA brand palette (Teal / Dark Teal / Gold / Light Teal / Cream),
sampled from the XIA logo and value-proposition deck (visualization-builder
skill). Reused as-is across every project so the whole portfolio reads as one
coherent, on-brand design system, the same way a real XIA engagement would
ship consistent-looking deliverables to a client. Gold is reserved for
one-per-view emphasis (the hero KPI, the answer) — never apply it to more
than one competing element. Never use Anthropic's "Claude clay" orange
(#D97757 family) as an accent, fill, or highlight.

Import this from any project's analysis.py to get matplotlib styling,
or import COLORS/STATUS from dashboard.py-generating scripts.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# ---- XIA brand palette -----------------------------------------------
TEAL = "#71A8A3"        # primary / brand — default series color
DARK_TEAL = "#163832"   # ink — text, titles, XIA's "black" (never pure #000)
GOLD = "#B8842C"        # accent — one-per-view emphasis (hero KPI, the answer)
LIGHT_TEAL = "#DCEAE7"  # tint — secondary series, card/gridline base
CREAM = "#F6EFE1"       # page background instead of pure white

# ---- Categorical palette (fixed order — never re-cycled) -----------------
# Base teal + gold accent + grays desaturated from teal, per the brand rule.
CATEGORICAL = [
    TEAL,        # 1 teal (primary)
    GOLD,        # 2 gold (accent)
    DARK_TEAL,   # 3 dark teal
    "#9CB8B4",   # 4 muted teal-gray
    "#D4A94F",   # 5 light gold
    "#4F6360",   # 6 deep teal-gray
    "#C7D6D3",   # 7 pale teal-gray
    "#8C6220",   # 8 deep gold / bronze
]

STATUS = {
    "good": "#3E8F72",      # teal-leaning green — on-brand "healthy"
    "warning": GOLD,
    "serious": "#8C5A1E",   # deep bronze — escalated warning, not clay-orange
    "critical": "#d03b3b",  # red — universal alarm, unrelated hue family
    "neutral": "#9CB8B4",   # muted teal-gray — stable/no-action-needed group
}

# Sequential teal: light tint -> dark teal, for funnels, heatmaps, gradients.
SEQUENTIAL_TEAL = ["#DCEAE7", "#BFDAD5", "#9FC7C0", "#71A8A3", "#548C86", "#39655F", "#163832"]

INK = {
    "surface": "#FFFFFF",
    "page": CREAM,
    "primary": DARK_TEAL,
    "secondary": "#4A625D",
    "muted": "#7E948F",
    "grid": DARK_TEAL,   # paired with grid.alpha below — never solid black
    "axis": "#9CB8B4",
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
        "grid.alpha": 0.2,
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
