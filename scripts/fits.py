"""Per-event measures and the three decay models. assets/fit.js implements the same
steps for the browser, line for line, so a curve fitted there matches one fitted here.
Keep the two in step; scripts/check_fit_parity.py compares them.

Series convention: an array of daily views for days -60 ... +365 around the event
(index 0 is day -60, index 60 is day 0). NaN marks days after the last available day.

Post-audit version, 2026-10-29 (docs/decisions.md, entries 26 to 31):
  - the decay models are fitted to every day after the peak, as log(1 + views) against
    log(1 + baseline + f(t)), instead of to log excess on days with positive excess only;
  - the main half-life compares the smoothed series with the smoothed peak;
  - an event with no spike on days 0 to 3 but one on days 4 to 30 is a "delayed spike";
  - an optional external baseline window (used for the Academy Awards).
"""
import math
import numpy as np

PRE, POST = 60, 365
BASE = (-60, -8)          # baseline window, inclusive
PEAK = (0, 3)             # peak window, inclusive
DELAY = (4, 30)           # where a late-reported spike is looked for
LIFT = (335, 365)         # lift window, inclusive
MIN_LIFT_DAYS = 21
MIN_FIT_DAYS = 30


def idx(day):
    return day + PRE


def dow_factors(vb, wd0):
    """Multiplicative day-of-week factors from a baseline series vb whose first day has
    weekday wd0 (0 = Monday): mean 1, clipped to [0.5, 2]."""
    wb = np.array([(wd0 + k) % 7 for k in range(len(vb))])
    m = np.nanmean(vb)
    f = np.ones(7)
    if m > 0:
        for d in range(7):
            x = vb[wb == d]
            if len(x):
                f[d] = np.clip(np.nanmean(x) / m, 0.5, 2.0)
        f = f / f.mean()
    return f


def smooth(x, win):
    """Centered rolling mean; NaN where the window is not complete."""
    out = np.full(len(x), np.nan)
    h = win // 2
    for i in range(h, len(x) - (win - 1 - h)):
        seg = x[i - h:i - h + win]
        if not np.isnan(seg).any():
            out[i] = seg.mean()
    return out


def cap_series(v, cap):
    """Cut any day above cap times the median of its six neighbors to that bound."""
    raw = v.copy()
    out = v.copy()
    n = 0
    for i in range(len(v)):
        nb = np.r_[raw[max(0, i - 3):i], raw[i + 1:i + 4]]
        nb = nb[~np.isnan(nb)]
        if len(nb) and not np.isnan(raw[i]):
            lim = cap * np.median(nb)
            if lim > 0 and raw[i] > lim:
                out[i] = lim
                n += 1
    return out, n


def first_below(x, start, level):
    for t in range(start + 1, len(x)):
        if not np.isnan(x[t]) and x[t] < level:
            return t - start
    return np.nan


def measures(views, weekday0, win=7, cap=None, base=None, peak=PEAK):
    """Baseline, peak, spike class, half-lives and lift for one event.
    base: optional (views, weekday0) of another window to take the baseline and the
    day-of-week factors from. peak: the window the peak is searched in."""
    v = np.asarray(views, dtype=float).copy()
    capped = 0
    if cap:
        v, capped = cap_series(v, cap)
    w = np.array([(weekday0 + k) % 7 for k in range(len(v))])
    if base is not None:
        bv = np.asarray(base[0], dtype=float)
        f = dow_factors(bv, base[1])
        bw = np.array([(base[1] + k) % 7 for k in range(len(bv))])
        baseline = float(np.nanmedian(bv / f[bw]))
    else:
        b = slice(idx(BASE[0]), idx(BASE[1]) + 1)
        f = dow_factors(v[b], weekday0)
        baseline = None
    a = v / f[w]
    if baseline is None:
        baseline = float(np.nanmedian(a[idx(BASE[0]):idx(BASE[1]) + 1]))
    pk = a[idx(peak[0]):idx(peak[1]) + 1]
    peak_day = int(np.nanargmax(pk)) + peak[0]
    pv = float(pk[peak_day - peak[0]])
    ex = a - baseline
    pex = pv - baseline
    spike = bool(baseline > 0 and pex > baseline)
    kind = "spike" if spike else "none"
    if not spike and baseline > 0 and peak == PEAK:
        late = a[idx(DELAY[0]):idx(DELAY[1]) + 1]
        if np.nanmax(late) > 2 * baseline:
            kind = "delayed"
    out = {"baseline": baseline, "peak": pv, "peak_day": peak_day, "peak_ratio": pv / baseline if baseline > 0 else np.nan,
           "spike": spike, "spike_kind": kind, "half_life": np.nan, "half_life_raw": np.nan, "half_life_spec": np.nan,
           "half_life_censored": False, "smooth_peak_day": np.nan, "cum_half_day": np.nan, "late_share": np.nan,
           "lift": np.nan, "capped_days": capped, "dow_amplitude": float(f.max() / f.min())}
    if pex > 0:
        sm = smooth(ex, win)
        spk = sm[idx(peak[0]):idx(peak[1]) + 1]
        if not np.all(np.isnan(spk)):
            sd = int(np.nanargmax(spk)) + peak[0]
            out["smooth_peak_day"] = sd
            out["half_life"] = first_below(sm, idx(sd), 0.5 * float(spk[sd - peak[0]]))
            out["half_life_censored"] = bool(np.isnan(out["half_life"]))
        out["half_life_raw"] = first_below(ex, idx(peak_day), 0.5 * pex)
        out["half_life_spec"] = first_below(sm, idx(peak_day), 0.5 * pex)
        tail = np.nan_to_num(ex[idx(peak_day):idx(POST) + 1].clip(min=0))
        cum = np.cumsum(tail)
        if cum[-1] > 0:
            out["cum_half_day"] = int(np.searchsorted(cum, 0.5 * cum[-1]))
            out["late_share"] = float(tail[8:].sum() / cum[-1])
    lw = a[idx(LIFT[0]):idx(LIFT[1]) + 1]
    lw = lw[~np.isnan(lw)]
    if baseline > 0 and len(lw) >= MIN_LIFT_DAYS:
        out["lift"] = float(np.median(lw)) / baseline
    return out, a, ex


# ---- decay models ----
# Every day after the peak counts. With a the adjusted views and b the baseline, the fit
# minimizes the squared difference between log(1 + a_t) and log(1 + b + f(t)), t = 1, 2, ...
# days after the peak, where f is the decay of the excess:
#   exp     A e^(-t/tau)
#   pow     A t^(-alpha)
#   biexp   A (w e^(-t/tau1) + (1 - w) e^(-t/tau2)),  tau1 < tau2
# Parameters live on log scales (log A, log tau, log alpha, logit w). A fixed grid gives
# the start and Nelder-Mead refines it.

def fit_points(a, peak_day):
    t = np.arange(1, POST - peak_day + 1, dtype=float)
    y = a[idx(peak_day) + 1:idx(POST) + 1]
    ok = ~np.isnan(y)
    return t[ok], np.log1p(np.maximum(y[ok], 0))


def curve(model, p, t):
    t = np.asarray(t, dtype=float)
    if model == "exp":
        return math.exp(p[0]) * np.exp(-t / math.exp(p[1]))
    if model == "pow":
        return math.exp(p[0]) * t ** (-math.exp(p[1]))
    w = 1 / (1 + math.exp(-p[3]))
    return math.exp(p[0]) * (w * np.exp(-t / math.exp(p[1])) + (1 - w) * np.exp(-t / math.exp(p[2])))


def rss(model, p, t, y, b):
    if model == "biexp" and not p[1] < p[2]:
        return math.inf
    r = y - np.log1p(b + curve(model, p, t))
    v = float((r * r).sum())
    return v if math.isfinite(v) else math.inf


def geom(a, b, n):
    return [a * (b / a) ** (i / (n - 1)) for i in range(n)]


DA = [-2 + 0.5 * i for i in range(9)]                 # log A offsets around the day-1 excess
TAU = geom(0.3, 3000, 30)
ALPHA = geom(0.05, 5, 30)
TAU1 = geom(0.3, 30, 10)
TAU2 = geom(3, 3000, 12)
WS = [1 - x for x in geom(1e-3, 0.5, 8)]


def grids(a0):
    """Starting grids in a fixed order; fit.js builds the same lists in the same order."""
    la = [math.log(a0) + d for d in DA]
    g = {"exp": [[x, math.log(tau)] for x in la for tau in TAU],
         "pow": [[x, math.log(al)] for x in la for al in ALPHA],
         "biexp": [[x, math.log(t1), math.log(t2), math.log(w / (1 - w))]
                   for x in la for t1 in TAU1 for t2 in TAU2 if t2 > 1.5 * t1 for w in WS]}
    return g


def grid_rss(model, G, t, y, b):
    """RSS for every grid row at once (vectorized form of rss())."""
    G = np.asarray(G)
    A = np.exp(G[:, :1])
    T = t[None, :]
    if model == "exp":
        f = A * np.exp(-T / np.exp(G[:, 1:2]))
    elif model == "pow":
        f = A * T ** (-np.exp(G[:, 1:2]))
    else:
        w = 1 / (1 + np.exp(-G[:, 3:4]))
        f = A * (w * np.exp(-T / np.exp(G[:, 1:2])) + (1 - w) * np.exp(-T / np.exp(G[:, 2:3])))
    r = y[None, :] - np.log1p(b + f)
    return (r * r).sum(axis=1)


def aic(r, n, k):
    return n * math.log(r / n) + 2 * (k + 1)


def nelder_mead(f, x0, step=0.3, iters=600, tol=1e-10):
    """Plain Nelder-Mead, written out so the browser version can match it exactly."""
    n = len(x0)
    pts = [list(x0)] + [[x0[j] + (step if j == i else 0) for j in range(n)] for i in range(n)]
    vals = [f(p) for p in pts]
    for _ in range(iters):
        order = sorted(range(n + 1), key=lambda i: vals[i])
        pts, vals = [pts[i] for i in order], [vals[i] for i in order]
        if abs(vals[-1] - vals[0]) <= tol * (abs(vals[0]) + tol):
            break
        c = [sum(p[j] for p in pts[:-1]) / n for j in range(n)]
        xr = [c[j] + (c[j] - pts[-1][j]) for j in range(n)]
        fr = f(xr)
        if fr < vals[0]:
            xe = [c[j] + 2 * (c[j] - pts[-1][j]) for j in range(n)]
            fe = f(xe)
            pts[-1], vals[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < vals[-2]:
            pts[-1], vals[-1] = xr, fr
        else:
            xc = [c[j] + 0.5 * (pts[-1][j] - c[j]) for j in range(n)]
            fc = f(xc)
            if fc < vals[-1]:
                pts[-1], vals[-1] = xc, fc
            else:
                for i in range(1, n + 1):
                    pts[i] = [pts[0][j] + 0.5 * (pts[i][j] - pts[0][j]) for j in range(n)]
                    vals[i] = f(pts[i])
    i = min(range(n + 1), key=lambda i: vals[i])
    return pts[i]


K = {"exp": 2, "pow": 2, "biexp": 4}


def fit_all(a, baseline, peak_day):
    t, y = fit_points(a, peak_day)
    n = len(t)
    if n < MIN_FIT_DAYS:
        return None
    a0 = max(float(a[idx(peak_day) + 1]) - baseline, 1.0) if not np.isnan(a[idx(peak_day) + 1]) else 1.0
    G = grids(a0)
    out = {"n": n, "params": {}, "rss": {}, "aic": {}}
    for m in ("exp", "pow", "biexp"):
        r = grid_rss(m, G[m], t, y, baseline)
        start = G[m][int(np.argmin(r))]
        p = nelder_mead(lambda q: rss(m, q, t, y, baseline), start)
        out["params"][m] = p
        out["rss"][m] = rss(m, p, t, y, baseline)
        out["aic"][m] = aic(out["rss"][m], n, K[m])
    out["best"] = min(out["aic"], key=out["aic"].get)
    return out


def describe(fit):
    """Readable parameters: A, tau, alpha, tau1, tau2, w."""
    p = fit["params"]
    return {"exp_A": math.exp(p["exp"][0]), "exp_tau": math.exp(p["exp"][1]),
            "pow_A": math.exp(p["pow"][0]), "pow_alpha": math.exp(p["pow"][1]),
            "bi_A": math.exp(p["biexp"][0]), "bi_tau1": math.exp(p["biexp"][1]), "bi_tau2": math.exp(p["biexp"][2]),
            "bi_w": 1 / (1 + math.exp(-p["biexp"][3]))}


# ---- legacy: the spec's comparison, kept only as a reported sensitivity row ----
# Fitted log excess on days with excess above zero. Dropping the days at or below the
# baseline biases the choice toward the biexponential: in simulation it picks the
# biexponential for most pure exponentials (tables/model_recovery.csv). Not used for results.

def fit_spec_logexcess(ex, peak_day):
    t = np.arange(1, POST - peak_day + 1, dtype=float)
    y = ex[idx(peak_day) + 1:idx(POST) + 1]
    ok = ~np.isnan(y) & (y > 0)
    t, y = t[ok], np.log(y[ok])
    n = len(t)
    if n < MIN_FIT_DAYS:
        return None

    def lin(x):
        b = np.polyfit(x, y, 1)
        return float(((y - np.polyval(b, x)) ** 2).sum())
    r = {"exp": lin(t), "pow": lin(np.log(t))}

    def bi(q):
        if not q[0] < q[1]:
            return math.inf
        w = 1 / (1 + math.exp(-q[2]))
        sh = w * np.exp(-t / math.exp(q[0])) + (1 - w) * np.exp(-t / math.exp(q[1]))
        if not np.all(sh > 0):
            return math.inf
        ls = np.log(sh)
        return float(((y - (y - ls).mean() - ls) ** 2).sum())
    best = min(([math.log(a), math.log(b), math.log(w / (1 - w))] for a in TAU1 for b in TAU2 if b > 1.5 * a
                for w in WS), key=bi)
    r["biexp"] = bi(nelder_mead(bi, best))
    a = {m: aic(r[m], n, K[m]) for m in r}
    return min(a, key=a.get)
