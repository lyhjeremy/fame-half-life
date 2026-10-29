"""Per-event measures and the three decay models. assets/fame.js implements the same
steps for the live lookup, line for line, so a curve fitted in the browser matches one
fitted here. Keep the two in step.

Series convention: an array of daily views for days -60 ... +365 around the event
(index 0 is day -60, index 60 is day 0). NaN marks days after the last available date.
"""
import math
import numpy as np

PRE, POST = 60, 365
BASE = (-60, -8)          # baseline window, inclusive
PEAK = (0, 3)             # peak window, inclusive
LIFT = (335, 365)         # lift window, inclusive
MIN_LIFT_DAYS = 21
MIN_FIT_DAYS = 30


def idx(day):
    return day + PRE


def dow_factors(views, weekday0):
    """Multiplicative day-of-week factors from the baseline window, mean 1, clipped to [0.5, 2].
    weekday0 is the weekday (0 = Monday) of day -60."""
    w = np.array([(weekday0 + k) % 7 for k in range(len(views))])
    b = slice(idx(BASE[0]), idx(BASE[1]) + 1)
    vb, wb = views[b], w[b]
    m = np.nanmean(vb)
    f = np.ones(7)
    if m > 0:
        for d in range(7):
            x = vb[wb == d]
            if len(x):
                f[d] = np.clip(np.nanmean(x) / m, 0.5, 2.0)
        f = f / f.mean()
    return f, w


def smooth(x, win):
    """Centered rolling mean; NaN where the window is not complete."""
    out = np.full(len(x), np.nan)
    h = win // 2
    for i in range(h, len(x) - (win - 1 - h)):
        seg = x[i - h:i - h + win]
        if not np.isnan(seg).any():
            out[i] = seg.mean()
    return out


def measures(views, weekday0, win=7, cap=None):
    """Baseline, peak, half-life and lift for one event. cap: if set, any day above
    cap times the median of its six neighbors (three each side) is cut to that bound."""
    v = np.asarray(views, dtype=float).copy()
    capped = 0
    if cap:
        raw = v.copy()
        for i in range(len(v)):
            nb = np.r_[raw[max(0, i - 3):i], raw[i + 1:i + 4]]
            nb = nb[~np.isnan(nb)]
            if len(nb) and not np.isnan(raw[i]):
                lim = cap * np.median(nb)
                if lim > 0 and raw[i] > lim:
                    v[i] = lim
                    capped += 1
    f, w = dow_factors(v, weekday0)
    a = v / f[w]
    base = float(np.nanmedian(a[idx(BASE[0]):idx(BASE[1]) + 1]))
    pk = a[idx(PEAK[0]):idx(PEAK[1]) + 1]
    peak_day = int(np.nanargmax(pk)) + PEAK[0]
    peak = float(pk[peak_day - PEAK[0]])
    ex = a - base
    pex = peak - base
    out = {"baseline": base, "peak": peak, "peak_day": peak_day, "peak_ratio": peak / base if base > 0 else np.nan,
           "spike": bool(base > 0 and pex > base), "half_life": np.nan, "half_life_censored": False,
           "lift": np.nan, "capped_days": capped, "dow_amplitude": float(f.max() / f.min())}
    if pex > 0:
        sm = smooth(ex, win)
        hl = np.nan
        for t in range(idx(peak_day) + 1, len(sm)):
            if not np.isnan(sm[t]) and sm[t] < 0.5 * pex:
                hl = t - idx(peak_day)
                break
        out["half_life"] = hl
        out["half_life_censored"] = bool(np.isnan(hl))
        # Day by which half of the first year's excess views (after the peak day) had arrived.
        tail = np.nan_to_num(ex[idx(peak_day):idx(POST) + 1].clip(min=0))
        cum = np.cumsum(tail)
        out["cum_half_day"] = int(np.searchsorted(cum, 0.5 * cum[-1])) if cum[-1] > 0 else np.nan
        # Share of those excess views that arrived more than a week after the peak day.
        out["late_share"] = float(tail[8:].sum() / cum[-1]) if cum[-1] > 0 else np.nan
    lw = a[idx(LIFT[0]):idx(LIFT[1]) + 1]
    lw = lw[~np.isnan(lw)]
    if base > 0 and len(lw) >= MIN_LIFT_DAYS:
        out["lift"] = float(np.median(lw)) / base
    return out, a, ex


# ---- decay models, fitted to log excess on the days after the peak ----

def fit_points(ex, peak_day):
    t = np.arange(1, POST - peak_day + 1, dtype=float)
    y = ex[idx(peak_day) + 1:idx(POST) + 1]
    ok = ~np.isnan(y) & (y > 0)
    return t[ok], np.log(y[ok])


def aic(rss, n, k):
    return n * math.log(rss / n) + 2 * (k + 1)


def ols(x, y):
    xm, ym = x.mean(), y.mean()
    sxx = ((x - xm) ** 2).sum()
    b = ((x - xm) * (y - ym)).sum() / sxx if sxx > 0 else 0.0
    return ym - b * xm, b


def fit_exp(t, y):
    a, b = ols(t, y)
    rss = float(((y - (a + b * t)) ** 2).sum())
    return {"A": math.exp(a), "tau": -1 / b if b < 0 else math.inf, "rss": rss}


def fit_pow(t, y):
    a, b = ols(np.log(t), y)
    rss = float(((y - (a + b * np.log(t))) ** 2).sum())
    return {"A": math.exp(a), "alpha": -b, "rss": rss}


def _biexp_rss(t, y, lt1, lt2, lw):
    t1, t2 = math.exp(lt1), math.exp(lt2)
    w = 1 / (1 + math.exp(-lw))
    shape = w * np.exp(-t / t1) + (1 - w) * np.exp(-t / t2)
    if not np.all(shape > 0):
        return math.inf, 0.0
    ls = np.log(shape)
    la = float((y - ls).mean())
    return float(((y - la - ls) ** 2).sum()), la


T1 = np.geomspace(0.3, 60, 16)
T2 = np.geomspace(3, 3000, 18)
W = 1 - np.geomspace(1e-4, 0.5, 14)


def fit_biexp(t, y):
    """Sum of two exponentials, A (w e^(-t/tau1) + (1 - w) e^(-t/tau2)), tau1 < tau2.
    A coarse grid gives the start; Nelder-Mead on (log tau1, log tau2, logit w) refines it."""
    best = (math.inf, None)
    for t1 in T1:
        for t2 in T2:
            if t2 <= t1 * 1.5:
                continue
            for w in W:
                r, _ = _biexp_rss(t, y, math.log(t1), math.log(t2), math.log(w / (1 - w)))
                if r < best[0]:
                    best = (r, [math.log(t1), math.log(t2), math.log(w / (1 - w))])
    p = nelder_mead(lambda q: _biexp_rss(t, y, *q)[0] if q[0] < q[1] else math.inf, best[1])
    rss, la = _biexp_rss(t, y, *p)
    t1, t2, w = math.exp(p[0]), math.exp(p[1]), 1 / (1 + math.exp(-p[2]))
    return {"A": math.exp(la), "tau1": t1, "tau2": t2, "w": w, "rss": rss}


def nelder_mead(f, x0, step=0.3, iters=400, tol=1e-9):
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


def fit_all(ex, peak_day):
    t, y = fit_points(ex, peak_day)
    n = len(t)
    if n < MIN_FIT_DAYS:
        return None
    e, p, b = fit_exp(t, y), fit_pow(t, y), fit_biexp(t, y)
    out = {"n": n, "exp": e, "pow": p, "biexp": b,
           "aic": {"exp": aic(e["rss"], n, 2), "pow": aic(p["rss"], n, 2), "biexp": aic(b["rss"], n, 4)}}
    out["best"] = min(out["aic"], key=out["aic"].get)
    return out


def model_curve(f, model, t):
    t = np.asarray(t, dtype=float)
    m = f[model]
    if model == "exp":
        return m["A"] * np.exp(-t / m["tau"])
    if model == "pow":
        return m["A"] * t ** (-m["alpha"])
    return m["A"] * (m["w"] * np.exp(-t / m["tau1"]) + (1 - m["w"]) * np.exp(-t / m["tau2"]))
