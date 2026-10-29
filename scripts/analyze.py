"""Per-event measures, curve fits, model comparison, regressions and checks.

Reads data/events.csv, data/fetch_log.csv and data/series.csv.gz.
Writes results/measures.csv, results/summary.json, results/avg_curve.csv and tables/*.csv.
"""
import datetime as dt, json, math, pathlib, sys, warnings
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import fits

ROOT = pathlib.Path(__file__).resolve().parent.parent
RES, TAB = ROOT / "results", ROOT / "tables"
warnings.filterwarnings("ignore", category=RuntimeWarning)


def award_family(a):
    if not isinstance(a, str) or not a:
        return ""
    for k in ("Nobel", "Academy Award", "Ballon", "Booker"):
        if k in a:
            return {"Nobel": "Nobel Prize", "Academy Award": "Academy Award", "Ballon": "Ballon d'Or",
                    "Booker": "Booker Prize"}[k]
    return a


def load():
    ev = pd.read_csv(ROOT / "data/events.csv", keep_default_na=False)
    lg = pd.read_csv(ROOT / "data/fetch_log.csv", keep_default_na=False)
    s = pd.read_csv(ROOT / "data/series.csv.gz", index_col="event_id")
    return ev, lg, s


def per_event(ev, s):
    rows, fitted, adj = [], {}, {}
    for i, r in enumerate(ev.itertuples()):
        if r.event_id not in s.index:
            continue
        v = s.loc[r.event_id].to_numpy(dtype=float)
        wd0 = (dt.date.fromisoformat(r.event_date) - dt.timedelta(days=fits.PRE)).weekday()
        m, a, ex = fits.measures(v, wd0)
        row = {"event_id": r.event_id, **m}
        for win in (3, 14):
            row[f"half_life_w{win}"] = fits.measures(v, wd0, win=win)[0]["half_life"]
        mc = fits.measures(v, wd0, cap=50)[0]
        row.update({"capped_days": mc["capped_days"], "half_life_capped": mc["half_life"],
                    "lift_capped": mc["lift"], "spike_capped": mc["spike"]})
        if m["spike"]:
            f = fits.fit_all(ex, m["peak_day"])
            if f:
                fitted[r.event_id] = f
                row.update({"fit_n": f["n"], "best_model": f["best"],
                            "aic_exp": f["aic"]["exp"], "aic_pow": f["aic"]["pow"], "aic_biexp": f["aic"]["biexp"],
                            "exp_A": f["exp"]["A"], "exp_tau": f["exp"]["tau"],
                            "pow_A": f["pow"]["A"], "pow_alpha": f["pow"]["alpha"],
                            "bi_A": f["biexp"]["A"], "bi_tau1": f["biexp"]["tau1"], "bi_tau2": f["biexp"]["tau2"],
                            "bi_w": f["biexp"]["w"]})
        rows.append(row)
        adj[r.event_id] = a / m["baseline"] if m["baseline"] > 0 else None
        if i % 200 == 0:
            print(f"measured {i}/{len(ev)}", flush=True)
    return pd.DataFrame(rows), fitted, adj


def ci(model, term):
    lo, hi = model.conf_int().loc[term]
    return model.params[term], lo, hi, model.pvalues[term]


def regressions(m):
    out = []
    specs = [
        ("log_half_life", "all", "log_half_life ~ C(event_type, Treatment('death')) + log_baseline + C(occupation_group, Treatment('screen')) + year"),
        ("log_lift", "all", "log_lift ~ C(event_type, Treatment('death')) + log_baseline + C(occupation_group, Treatment('screen')) + year"),
        ("log_half_life", "deaths", "log_half_life ~ log_baseline + age_at_event + C(occupation_group, Treatment('screen')) + year"),
        ("log_lift", "deaths", "log_lift ~ log_baseline + age_at_event + C(occupation_group, Treatment('screen')) + year"),
    ]
    fitted = {}
    for y, sample, f in specs:
        d = m.copy()
        if sample == "deaths":
            d = d[d.event_type == "death"]
        d = d.dropna(subset=[y, "log_baseline", "year"] + (["age_at_event"] if sample == "deaths" else []))
        d = d[np.isfinite(d[y])]
        mod = smf.ols(f, data=d).fit(cov_type="HC3")
        fitted[(y, sample)] = mod
        for term in mod.params.index:
            b, lo, hi, p = ci(mod, term)
            out.append({"outcome": y, "sample": sample, "term": term, "coef": b, "ci_low": lo, "ci_high": hi,
                        "p": p, "n": int(mod.nobs), "r2": mod.rsquared})
    return pd.DataFrame(out), fitted


def main():
    ev, lg, s = load()
    kept = ev[ev.excluded_reason == ""]
    m, fitted, adj = per_event(kept, s)
    m = kept[["event_id", "qid", "title", "event_type", "award", "event_date", "sitelinks", "occupation_group",
              "age_at_event"]].merge(m, on="event_id")
    m["age_at_event"] = pd.to_numeric(m.age_at_event, errors="coerce")
    m["award_family"] = m.award.map(award_family)
    m["year"] = m.event_date.str[:4].astype(int)
    m["log_baseline"] = np.log(m.baseline.where(m.baseline > 0))
    m["log_half_life"] = np.log(m.half_life.where(m.half_life > 0))
    m["log_lift"] = np.log(m.lift.where(m.lift > 0))

    # Events with no baseline traffic cannot have a ratio; dropped and counted.
    nobase = m[~(m.baseline >= 1)]
    m = m[m.baseline >= 1].copy()
    m.drop(columns=["log_half_life", "log_lift"]).to_csv(RES / "measures.csv", index=False, float_format="%.6g")

    # ---- counts and drops ----
    drops = lg[lg.drop_reason != ""].drop_reason.value_counts().to_dict()
    drops["baseline under 1 view a day"] = len(nobase)
    counts = {
        "candidates": ev.groupby("event_type").size().to_dict(),
        "excluded": ev[ev.excluded_reason != ""].groupby(["event_type", "excluded_reason"]).size()
                      .rename("n").reset_index().to_dict("records"),
        "fetch_drops": lg.merge(ev[["event_id", "event_type"]], on="event_id")
                         .query("drop_reason != ''").groupby(["event_type", "drop_reason"]).size()
                         .rename("n").reset_index().to_dict("records"),
        "no_baseline": nobase.groupby("event_type").size().to_dict(),
        "analyzed": m.groupby("event_type").size().to_dict(),
        "analyzed_awards": m[m.event_type == "award"].groupby("award_family").size().to_dict(),
        "title_changed_since_freeze": int(lg.title_changed.astype(str).eq("True").sum()),
    }

    # ---- EDA ----
    def q(x, p):
        x = x.dropna()
        return float(np.percentile(x, p)) if len(x) else None

    eda = {}
    for t, g in [("all", m), ("death", m[m.event_type == "death"]), ("award", m[m.event_type == "award"])]:
        sp = g[g.spike]
        eda[t] = {
            "n": len(g), "n_spike": int(g.spike.sum()), "share_no_spike": float(1 - g.spike.mean()),
            "baseline_median": q(g.baseline, 50), "baseline_p25": q(g.baseline, 25), "baseline_p75": q(g.baseline, 75),
            "peak_ratio_median": q(g.peak_ratio, 50), "peak_ratio_p25": q(g.peak_ratio, 25), "peak_ratio_p75": q(g.peak_ratio, 75),
            "peak_day_shares": g.peak_day.value_counts(normalize=True).sort_index().to_dict(),
            "half_life_median": q(sp.half_life, 50), "half_life_p25": q(sp.half_life, 25), "half_life_p75": q(sp.half_life, 75),
            "half_life_mean": float(sp.half_life.mean()),
            "half_life_censored": int(sp.half_life_censored.sum()),
            "half_life_dist": sp.half_life.value_counts().sort_index().head(10).to_dict(),
            "cum_half_median": q(sp.cum_half_day, 50), "cum_half_p25": q(sp.cum_half_day, 25), "cum_half_p75": q(sp.cum_half_day, 75),
            "late_share_median": q(sp.late_share, 50), "late_share_p25": q(sp.late_share, 25), "late_share_p75": q(sp.late_share, 75),
            "lift_n": int(g.lift.notna().sum()),
            "lift_median": q(g.lift, 50), "lift_p25": q(g.lift, 25), "lift_p75": q(g.lift, 75),
            "lift_share_above1": float((g.lift.dropna() > 1).mean()),
            "lift_share_above2": float((g.lift.dropna() > 2).mean()),
            "lift_median_spike": q(sp.lift, 50),
            "dow_amplitude_median": q(g.dow_amplitude, 50),
        }
    for fam, g in m[m.event_type == "award"].groupby("award_family"):
        eda[fam] = {"n": len(g), "share_no_spike": float(1 - g.spike.mean()),
                    "half_life_median": q(g[g.spike].half_life, 50), "lift_median": q(g.lift, 50),
                    "peak_ratio_median": q(g.peak_ratio, 50)}

    # ---- model comparison ----
    fm = m[m.best_model.notna()]
    wins = []
    for t, g in [("all", fm), ("death", fm[fm.event_type == "death"]), ("award", fm[fm.event_type == "award"])]:
        vc = g.best_model.value_counts(normalize=True)
        wins.append({"sample": t, "n": len(g), **{k: float(vc.get(k, 0)) for k in ("exp", "pow", "biexp")}})
    wins = pd.DataFrame(wins)
    wins.to_csv(TAB / "model_wins.csv", index=False, float_format="%.4f")
    d_aic = {
        "biexp_minus_pow_median": float((fm.aic_biexp - fm.aic_pow).median()),
        "biexp_minus_exp_median": float((fm.aic_biexp - fm.aic_exp).median()),
        "pow_minus_exp_median": float((fm.aic_pow - fm.aic_exp).median()),
        "share_biexp_beats_pow_by_10": float(((fm.aic_pow - fm.aic_biexp) > 10).mean()),
        "share_pow_beats_exp": float((fm.aic_pow < fm.aic_exp).mean()),
        "bi_tau1_median": float(fm.bi_tau1.median()), "bi_tau2_median": float(fm.bi_tau2.median()),
        "bi_w_median": float(fm.bi_w.median()), "pow_alpha_median": float(fm.pow_alpha.median()),
        "fit_n_median": float(fm.fit_n.median()), "n_fitted": len(fm),
        "n_spike_not_fitted": int(m.spike.sum() - len(fm)),
    }
    for t in ("death", "award"):
        g = fm[fm.event_type == t]
        d_aic[f"bi_tau1_median_{t}"] = float(g.bi_tau1.median())
        d_aic[f"bi_tau2_median_{t}"] = float(g.bi_tau2.median())
        d_aic[f"pow_alpha_median_{t}"] = float(g.pow_alpha.median())

    # ---- averaged curves: median views as a multiple of baseline, by day ----
    days = np.arange(-fits.PRE, fits.POST + 1)
    cur = {"day": days}
    for t in ("death", "award"):
        ids = m[(m.event_type == t)].event_id
        mat = np.vstack([adj[i] for i in ids if adj.get(i) is not None])
        cur[f"{t}_median"] = np.nanmedian(mat, axis=0)
        cur[f"{t}_p25"] = np.nanpercentile(mat, 25, axis=0)
        cur[f"{t}_p75"] = np.nanpercentile(mat, 75, axis=0)
        cur[f"{t}_n"] = (~np.isnan(mat)).sum(axis=0)
    cur = pd.DataFrame(cur)
    cur.to_csv(RES / "avg_curve.csv", index=False, float_format="%.5g")
    avg = {}
    for t in ("death", "award"):
        c = cur.set_index("day")[f"{t}_median"]
        pk_day = int(c.loc[0:3].idxmax())
        pk = float(c.loc[pk_day])
        half = next((d for d in range(pk_day + 1, fits.POST + 1) if c.loc[d] - 1 < 0.5 * (pk - 1)), None)
        tenth = next((d for d in range(pk_day + 1, fits.POST + 1) if c.loc[d] - 1 < 0.1 * (pk - 1)), None)
        avg[t] = {"peak_multiple": pk, "peak_day": pk_day, "half_day": half - pk_day if half else None,
                  "tenth_day": tenth - pk_day if tenth else None,
                  "day30": float(c.loc[30]), "day90": float(c.loc[90]), "day180": float(c.loc[180]),
                  "end_month": float(c.loc[335:365].median())}

    # ---- regressions ----
    reg, regm = regressions(m)
    reg.to_csv(TAB / "regressions.csv", index=False, float_format="%.5g")

    def term(y, sample, t):
        r = reg[(reg.outcome == y) & (reg["sample"] == sample) & (reg.term == t)]
        return r.iloc[0].to_dict() if len(r) else None
    award_t = "C(event_type, Treatment('death'))[T.award]"
    regsum = {k: {"award": term(y, "all", award_t), "log_baseline": term(y, "all", "log_baseline"),
                  "year": term(y, "all", "year"), "n": int(regm[(y, "all")].nobs), "r2": regm[(y, "all")].rsquared}
              for k, y in (("half_life", "log_half_life"), ("lift", "log_lift"))}
    for k, y in (("half_life", "log_half_life"), ("lift", "log_lift")):
        regsum[k]["age"] = term(y, "deaths", "age_at_event")
        regsum[k]["deaths_n"] = int(regm[(y, "deaths")].nobs)
        regsum[k]["deaths_r2"] = regm[(y, "deaths")].rsquared

    # ---- occupation table ----
    occ = (m.groupby(["event_type", "occupation_group"])
             .agg(n=("event_id", "size"), spikes=("spike", "sum"),
                  half_life_median=("half_life", "median"), cum_half_median=("cum_half_day", "median"),
                  late_share_median=("late_share", "median"), lift_median=("lift", "median"), baseline_median=("baseline", "median"),
                  peak_ratio_median=("peak_ratio", "median")).reset_index())
    occ.to_csv(TAB / "by_occupation.csv", index=False, float_format="%.4g")
    fam = (m.assign(group=np.where(m.event_type == "death", "Death", m.award_family))
             .groupby("group").agg(n=("event_id", "size"), share_spike=("spike", "mean"),
                                   half_life_median=("half_life", "median"), cum_half_median=("cum_half_day", "median"),
                                   late_share_median=("late_share", "median"), lift_median=("lift", "median"), peak_ratio_median=("peak_ratio", "median"),
                                   baseline_median=("baseline", "median")).reset_index())
    fam.to_csv(TAB / "by_event_group.csv", index=False, float_format="%.4g")

    # ---- checks ----
    sens = []
    for t, g in [("all", m), ("death", m[m.event_type == "death"]), ("award", m[m.event_type == "award"])]:
        sp = g[g.spike]
        sens.append({"sample": t, "w3": sp.half_life_w3.median(), "w7": sp.half_life.median(),
                     "w14": sp.half_life_w14.median(), "w3_mean": sp.half_life_w3.mean(), "w7_mean": sp.half_life.mean(),
                     "w14_mean": sp.half_life_w14.mean()})
    sens = pd.DataFrame(sens)
    sens.to_csv(TAB / "smoothing_sensitivity.csv", index=False, float_format="%.4g")
    bot = {
        "events_with_capped_day": int((m.capped_days > 0).sum()),
        "capped_days_total": int(m.capped_days.sum()),
        "half_life_median_capped": {t: float(m[(m.event_type == t) & m.spike_capped].half_life_capped.median()) for t in ("death", "award")},
        "lift_median_capped": {t: float(m[m.event_type == t].lift_capped.median()) for t in ("death", "award")},
        "spike_share_capped": {t: float(m[m.event_type == t].spike_capped.mean()) for t in ("death", "award")},
        "half_life_changed": int(((m.half_life != m.half_life_capped) & m.spike).sum()),
    }

    summary = {"counts": counts, "drops": drops, "eda": eda, "model_wins": wins.to_dict("records"), "aic": d_aic,
               "avg_curve": avg, "regressions": regsum, "smoothing": sens.to_dict("records"), "bot_check": bot,
               "last_data_day": "2026-10-27"}
    (RES / "summary.json").write_text(json.dumps(summary, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)) + "\n")
    print(json.dumps({"counts": counts["analyzed"], "eda_all": eda["death"], "award": eda["award"], "wins": wins.to_dict("records"),
                      "avg": avg, "smoothing": sens.to_dict("records"), "bot": bot}, indent=1, default=str))


if __name__ == "__main__":
    main()
