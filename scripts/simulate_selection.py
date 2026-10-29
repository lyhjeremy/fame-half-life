"""Can the model selector tell the three decay shapes apart? (post-audit check, 2026-10-29)

Simulates daily series with a known decay (pure exponential, pure power law, or a true
biexponential), runs them through the same measures and fits as the real data, and
records how often the lowest-AIC model is the true one, for the post-audit fit and for the
spec's original log-excess fit on positive days. Writes tables/model_recovery.csv.

Each series: baseline b drawn log-uniformly from 20 to 2,000 views a day; a weekly
pattern; a spike starting on day 0 with amplitude 50 to 500 times b; counts drawn as
Poisson around the mean times a lognormal day effect (sigma 0.15 and 0.30).
"""
import pathlib, sys
import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import fits

ROOT = pathlib.Path(__file__).resolve().parent.parent
N = 150


def series(rng, truth, sigma):
    days = np.arange(-fits.PRE, fits.POST + 1)
    b = float(np.exp(rng.uniform(np.log(20), np.log(2000))))
    amp = rng.uniform(1.0, 1.5)
    week = 1 + (amp - 1) * np.sin(2 * np.pi * (np.arange(7) / 7 + rng.uniform()))
    A = b * rng.uniform(50, 500)
    t = np.where(days >= 0, days + 1, np.nan).astype(float)
    if truth == "exp":
        f = A * np.exp(-t / rng.uniform(1, 8))
    elif truth == "pow":
        f = A * t ** (-rng.uniform(0.6, 1.6))
    else:
        slow = rng.uniform(0.01, 0.05)
        f = A * ((1 - slow) * np.exp(-t / rng.uniform(1, 5)) + slow * np.exp(-t / rng.uniform(40, 400)))
    mu = (b + np.nan_to_num(f)) * week[(np.arange(len(days))) % 7]
    v = rng.poisson(mu * rng.lognormal(0, sigma, len(days))).astype(float)
    return v


def main():
    rng = np.random.default_rng(20261029)
    rows = []
    for sigma in (0.15, 0.30):
        for truth in ("exp", "pow", "biexp"):
            picks, legacy = [], []
            for _ in range(N):
                v = series(rng, truth, sigma)
                m, a, ex = fits.measures(v, 0)
                f = fits.fit_all(a, m["baseline"], m["peak_day"]) if m["spike"] else None
                picks.append(f["best"] if f else "none")
                legacy.append(fits.fit_spec_logexcess(ex, m["peak_day"]) if m["spike"] else "none")
            s = pd.Series(picks).value_counts(normalize=True)
            rows.append({"noise_sigma": sigma, "truth": truth, "n": N, "recovered": float(s.get(truth, 0)),
                         **{f"picked_{k}": float(s.get(k, 0)) for k in ("exp", "pow", "biexp", "none")},
                         "spec_method_recovered": float(np.mean([x == truth for x in legacy])),
                         "spec_method_picked_biexp": float(np.mean([x == "biexp" for x in legacy]))})
            print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(ROOT / "tables/model_recovery.csv", index=False, float_format="%.4f")


if __name__ == "__main__":
    main()
