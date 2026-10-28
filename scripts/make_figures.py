"""Static figures for the README and the write-up's no-script fallback: figures/*.png."""
import json, pathlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIG = ROOT / "figures"
RED, BLUE, GRAY, INK, INK2, RULE, PAPER = "#9E3A2C", "#284B73", "#757A80", "#1B1E24", "#4F5560", "#C8C9C2", "#EEEDE6"
plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["IBM Plex Sans", "Helvetica Neue", "Arial"],
                     "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
                     "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": PAPER,
                     "axes.facecolor": PAPER, "savefig.facecolor": PAPER, "font.size": 11})


def avg_curve():
    c = pd.read_csv(ROOT / "results/avg_curve.csv")
    fig, ax = plt.subplots(figsize=(8.6, 4.6), dpi=150)
    for t, col, lab in (("death", RED, "Deaths"), ("award", BLUE, "Awards")):
        ax.fill_between(c.day, c[f"{t}_p25"], c[f"{t}_p75"], color=col, alpha=.12, lw=0)
        ax.plot(c.day, c[f"{t}_median"], color=col, lw=1.8, label=lab)
    ax.axhline(1, color=GRAY, lw=1, ls="--")
    ax.set_yscale("log")
    ax.set_xlim(-60, 365)
    ax.set_xlabel("Days from the event")
    ax.set_ylabel("Daily views, multiple of baseline")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}x"))
    ax.grid(axis="y", color=RULE, lw=.8)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIG / "average_curve.png")
    plt.close(fig)


def model_wins():
    w = pd.read_csv(ROOT / "tables/model_wins.csv").set_index("sample").loc[["all", "death", "award"]]
    fig, ax = plt.subplots(figsize=(8.6, 2.8), dpi=150)
    labels = {"all": "All events", "death": "Deaths", "award": "Awards"}
    left = np.zeros(len(w))
    for k, col, lab in (("biexp", BLUE, "Biexponential"), ("pow", RED, "Power law"), ("exp", GRAY, "Exponential")):
        ax.barh([f"{labels[i]} (n={int(w.loc[i, 'n'])})" for i in w.index], w[k], left=left, color=col, label=lab, height=.6)
        for j, (l, v) in enumerate(zip(left, w[k])):
            if v > .06:
                ax.text(l + v / 2, j, f"{100 * v:.0f}%", ha="center", va="center", color=PAPER, fontsize=10)
        left += w[k].to_numpy()
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1))
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(.5, -.18))
    fig.tight_layout()
    fig.savefig(FIG / "model_wins.png")
    plt.close(fig)


def lift():
    m = pd.read_csv(ROOT / "results/measures.csv")
    bins = np.geomspace(1 / 8, 64, 28)
    fig, ax = plt.subplots(figsize=(8.6, 3.8), dpi=150)
    for t, col, lab in (("death", RED, "Deaths"), ("award", BLUE, "Awards")):
        x = m[(m.event_type == t)].lift.dropna().clip(bins[0], bins[-1])
        h, _ = np.histogram(x, bins=bins)
        ax.step(bins[:-1], h / h.sum(), where="post", color=col, lw=1.8, label=f"{lab} (n={len(x)})")
    ax.axvline(1, color=GRAY, lw=1, ls="--")
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}x"))
    ax.set_xlabel("Views a year later (days 335 to 365) as a multiple of baseline")
    ax.set_ylabel("Share of events")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.grid(axis="y", color=RULE, lw=.8)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIG / "lift.png")
    plt.close(fig)


if __name__ == "__main__":
    FIG.mkdir(exist_ok=True)
    avg_curve(); model_wins(); lift()
    print("figures written")
