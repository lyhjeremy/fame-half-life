"""Per-event measures, curve fits, model comparison, regressions and checks.

Reads data/events.csv, data/fetch_log.csv, data/series.csv.gz and data/oscar_base.csv.gz
(the last two are rebuilt from the cache by fetch_pageviews.py).
Writes results/measures.csv, results/summary.json, results/avg_curve.csv and tables/*.csv.

Post-audit version, 2026-10-29: see docs/decisions.md, entries 26 to 33.
"""
import datetime as dt, json, pathlib, sys, warnings
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import fits

ROOT = pathlib.Path(__file__).resolve().parent.parent
RES, TAB = ROOT / "results", ROOT / "tables"
warnings.filterwarnings("ignore", category=RuntimeWarning)
FAMILY = {"Nobel": "Nobel Prize", "Academy Award": "Academy Award", "Ballon": "Ballon d'Or", "Booker": "Booker Prize"}


def award_family(a):
    for k, v in FAMILY.items():
        if isinstance(a, str) and k in a:
            return v
    return ""


def weekday0(event_date):
    return (dt.date.fromisoformat(event_date) - dt.timedelta(days=fits.PRE)).weekday()


def load_windows(name):
    out = {}
    p = ROOT / f"data/{name}.csv.gz"
    if p.exists():
        b = pd.read_csv(p)
        cols = [c for c in b.columns if c.startswith("b") and c[1:].isdigit()]
        for r in b.itertuples(index=False):
            d = r._asdict()
            out[d["event_id"]] = (np.array([d[c] for c in cols], dtype=float), dt.date.fromisoformat(d["start"]).weekday())
    return out


def load_series():
    s = pd.read_csv(ROOT / "data/series.csv.gz", index_col="event_id")
    return s, load_windows("oscar_base")


def per_event(ev, s, bases):
    rows, adj = [], {}
    early = load_windows("oscar_early")
    for i, r in enumerate(ev.itertuples()):
        if r.event_id not in s.index:
            continue
        v = s.loc[r.event_id].to_numpy(dtype=float)
        wd0 = weekday0(r.event_date)
        base = bases.get(r.event_id)
        m, a, ex = fits.measures(v, wd0, base=base)
        row = {"event_id": r.event_id, **m, "preseason_baseline": base is not None}
        for win in (3, 14):
            row[f"half_life_w{win}"] = fits.measures(v, wd0, win=win, base=base)[0]["half_life"]
        p30 = fits.measures(v, wd0, base=base, peak=(0, 30))[0]
        row.update({"p30_spike": p30["spike"], "p30_peak_day": p30["peak_day"], "p30_peak_ratio": p30["peak_ratio"],
                    "p30_half_life": p30["half_life"], "p30_late_share": p30["late_share"]})
        if base is not None:
            sp = fits.measures(v, wd0)[0]
            row.update({"spec_baseline": sp["baseline"], "spec_lift": sp["lift"], "spec_peak_ratio": sp["peak_ratio"]})
            if r.event_id in early:
                ea = fits.measures(v, wd0, base=early[r.event_id])[0]
                row.update({"early_baseline": ea["baseline"], "early_lift": ea["lift"]})
        mc = fits.measures(v, wd0, cap=50, base=base)[0]
        row.update({"capped_days": mc["capped_days"], "half_life_capped": mc["half_life"],
                    "lift_capped": mc["lift"], "spike_capped": mc["spike"]})
        if m["spike"]:
            f = fits.fit_all(a, m["baseline"], m["peak_day"])
            if f:
                row.update({"fit_n": f["n"], "best_model": f["best"], "aic_exp": f["aic"]["exp"],
                            "aic_pow": f["aic"]["pow"], "aic_biexp": f["aic"]["biexp"], **fits.describe(f)})
            row["spec_fit_best"] = fits.fit_spec_logexcess(ex, m["peak_day"])
        rows.append(row)
        adj[r.event_id] = a / m["baseline"] if m["baseline"] > 0 else None
        if i % 250 == 0:
            print(f"measured {i}/{len(ev)}", flush=True)
    return pd.DataFrame(rows), adj


def regressions(m):
    out, fitted = [], {}
    specs = [
        ("log_half_life", "all", "log_half_life ~ C(event_type, Treatment('death')) + log_baseline + C(occupation_group, Treatment('screen')) + year"),
        ("log_lift", "all", "log_lift ~ C(event_type, Treatment('death')) + log_baseline + C(occupation_group, Treatment('screen')) + year"),
        ("log_lift_spec", "all", "log_lift_spec ~ C(event_type, Treatment('death')) + log_baseline_spec + C(occupation_group, Treatment('screen')) + year"),
        ("log_half_life", "deaths", "log_half_life ~ log_baseline + age_at_event + C(occupation_group, Treatment('screen')) + year"),
        ("log_lift", "deaths", "log_lift ~ log_baseline + age_at_event + C(occupation_group, Treatment('screen')) + year"),
    ]
    for y, sample, f in specs:
        d = m[m.event_type == "death"] if sample == "deaths" else m
        need = [c for c in (y, "year", "age_at_event" if sample == "deaths" else None) if c]
        d = d.dropna(subset=need)
        d = d[np.isfinite(d[y])]
        mod = smf.ols(f, data=d).fit(cov_type="HC3")
        fitted[(y, sample)] = mod
        ci = mod.conf_int()
        for term in mod.params.index:
            out.append({"outcome": y, "sample": sample, "term": term, "coef": mod.params[term],
                        "ci_low": ci.loc[term, 0], "ci_high": ci.loc[term, 1], "p": mod.pvalues[term],
                        "n": int(mod.nobs), "r2": mod.rsquared})
    return pd.DataFrame(out), fitted


def q(x, p):
    x = pd.Series(x).dropna()
    return float(np.percentile(x, p)) if len(x) else None


def main():
    ev = pd.read_csv(ROOT / "data/events.csv", keep_default_na=False)
    lg = pd.read_csv(ROOT / "data/fetch_log.csv", keep_default_na=False)
    s, bases = load_series()
    kept = ev[ev.excluded_reason == ""]
    m, adj = per_event(kept, s, bases)
    m = kept[["event_id", "qid", "title", "event_type", "award", "event_date", "sitelinks", "occupation_group",
              "age_at_event"]].merge(m, on="event_id")
    m["age_at_event"] = pd.to_numeric(m.age_at_event, errors="coerce")
    m["award_family"] = m.award.map(award_family)
    m["year"] = m.event_date.str[:4].astype(int)
    nobase = m[~(m.baseline >= 1)]
    m = m[m.baseline >= 1].copy()
    m["spec_baseline"] = m.spec_baseline.where(m.preseason_baseline, m.baseline)
    m["spec_lift"] = m.spec_lift.where(m.preseason_baseline, m.lift)
    for c, src in (("log_baseline", "baseline"), ("log_baseline_spec", "spec_baseline"), ("log_half_life", "half_life"),
                   ("log_lift", "lift"), ("log_lift_spec", "spec_lift")):
        m[c] = np.log(m[src].where(m[src] > 0))
    m.drop(columns=[c for c in m.columns if c.startswith("log_")]).to_csv(RES / "measures.csv", index=False, float_format="%.6g")

    # ---- counts ----
    fd = lg.merge(ev[["event_id", "event_type"]], on="event_id").query("drop_reason != ''")
    counts = {
        "candidates": ev.groupby("event_type").size().to_dict(),
        "excluded": ev[ev.excluded_reason != ""].groupby(["event_type", "excluded_reason"]).size().rename("n").reset_index().to_dict("records"),
        "fetch_drops": fd.groupby(["event_type", "drop_reason"]).size().rename("n").reset_index().to_dict("records"),
        "no_baseline": nobase.groupby("event_type").size().to_dict(),
        "analyzed": m.groupby("event_type").size().to_dict(),
        "analyzed_awards": m[m.event_type == "award"].groupby("award_family").size().to_dict(),
        "title_from_later_move": int(((lg.title_used != lg.current_title) & (lg.drop_reason == "")).sum()),
        "amended_rows": int(ev.date_source.str.contains("corrected 2026-10-29").sum()),
        "spike_kinds": m.groupby(["event_type", "spike_kind"]).size().rename("n").reset_index().to_dict("records"),
    }
    dd = json.loads((ROOT / "data/events_dropped_dates.json").read_text())

    # ---- EDA by group ----
    def block(g):
        sp = g[g.spike]
        return {
            "n": len(g), "n_spike": int(g.spike.sum()), "n_delayed": int((g.spike_kind == "delayed").sum()),
            "n_none": int((g.spike_kind == "none").sum()),
            "baseline_median": q(g.baseline, 50), "baseline_p25": q(g.baseline, 25), "baseline_p75": q(g.baseline, 75),
            "peak_ratio_median": q(sp.peak_ratio, 50), "peak_ratio_p25": q(sp.peak_ratio, 25), "peak_ratio_p75": q(sp.peak_ratio, 75),
            "peak_day_shares": sp.peak_day.value_counts(normalize=True).sort_index().to_dict(),
            "half_life_median": q(sp.half_life, 50), "half_life_p25": q(sp.half_life, 25), "half_life_p75": q(sp.half_life, 75),
            "half_life_censored": int(sp.half_life_censored.sum()),
            "half_life_dist": sp.half_life.value_counts(normalize=True).sort_index().head(8).to_dict(),
            "half_life_raw_median": q(sp.half_life_raw, 50), "half_life_spec_median": q(sp.half_life_spec, 50),
            "half_life_spec_share1": float((sp.half_life_spec == 1).mean()) if len(sp) else None,
            "half_life_raw_share1": float((sp.half_life_raw == 1).mean()) if len(sp) else None,
            "half_life_share1": float((sp.half_life == 1).mean()) if len(sp) else None,
            "late_share_median": q(sp.late_share, 50), "late_share_p25": q(sp.late_share, 25), "late_share_p75": q(sp.late_share, 75),
            "lift_n": int(g.lift.notna().sum()), "lift_median": q(g.lift, 50), "lift_p25": q(g.lift, 25), "lift_p75": q(g.lift, 75),
            "lift_share_above1": float((g.lift.dropna() > 1).mean()), "spec_lift_median": q(g.spec_lift, 50),
            "spec_baseline_median": q(g.spec_baseline, 50), "dow_amplitude_median": q(g.dow_amplitude, 50),
        }
    eda = {"all": block(m), "death": block(m[m.event_type == "death"]), "award": block(m[m.event_type == "award"])}
    for fam, g in m[m.event_type == "award"].groupby("award_family"):
        eda[fam] = block(g)

    # ---- model comparison and its validation ----
    fm = m[m.best_model.notna()]
    wins = []
    for t, g in [("all", fm), ("death", fm[fm.event_type == "death"]), ("award", fm[fm.event_type == "award"])]:
        vc, lv = g.best_model.value_counts(normalize=True), g.spec_fit_best.value_counts(normalize=True)
        wins.append({"sample": t, "n": len(g), **{k: float(vc.get(k, 0)) for k in ("exp", "pow", "biexp")},
                     **{f"spec_{k}": float(lv.get(k, 0)) for k in ("exp", "pow", "biexp")}})
    wins = pd.DataFrame(wins)
    wins.to_csv(TAB / "model_wins.csv", index=False, float_format="%.4f")
    rec = pd.read_csv(TAB / "model_recovery.csv") if (TAB / "model_recovery.csv").exists() else None
    second = lambda r: sorted([r.aic_exp, r.aic_pow, r.aic_biexp])[1] - min(r.aic_exp, r.aic_pow, r.aic_biexp)
    bi = fm[fm.best_model == "biexp"]
    models = {
        "n_fitted": len(fm), "n_spike_not_fitted": int(m.spike.sum() - len(fm)),
        "margin_median": float(fm.apply(second, axis=1).median()),
        "share_margin_over_10": float((fm.apply(second, axis=1) > 10).mean()),
        "share_pow_beats_exp": float((fm.aic_pow < fm.aic_exp).mean()),
        "exp_tau_median": float(fm[fm.best_model == "exp"].exp_tau.median()) if (fm.best_model == "exp").any() else None,
        "pow_alpha_median": float(fm[fm.best_model == "pow"].pow_alpha.median()) if (fm.best_model == "pow").any() else None,
        "bi_tau1_median": float(bi.bi_tau1.median()) if len(bi) else None,
        "bi_tau2_median": float(bi.bi_tau2.median()) if len(bi) else None,
        "bi_slow_share_median": float((1 - bi.bi_w).median()) if len(bi) else None,
        "bi_tau2_over_365": float((bi.bi_tau2 > 365).mean()) if len(bi) else None,
        "recovery": rec.to_dict("records") if rec is not None else [],
    }

    # ---- averaged curves ----
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
                  "tenth_day": tenth - pk_day if tenth else None, "day30": float(c.loc[30]),
                  "end_month": float(c.loc[335:364].median()), "day365": float(c.loc[365])}

    # ---- regressions ----
    reg, regm = regressions(m)
    reg.to_csv(TAB / "regressions.csv", index=False, float_format="%.5g")

    def term(y, sample, t):
        r = reg[(reg.outcome == y) & (reg["sample"] == sample) & (reg.term == t)]
        return r.iloc[0].to_dict() if len(r) else None
    aw = "C(event_type, Treatment('death'))[T.award]"
    regsum = {}
    for k, y, base in (("half_life", "log_half_life", "log_baseline"), ("lift", "log_lift", "log_baseline"),
                       ("lift_spec", "log_lift_spec", "log_baseline_spec")):
        regsum[k] = {"award": term(y, "all", aw), "log_baseline": term(y, "all", base), "year": term(y, "all", "year"),
                     "n": int(regm[(y, "all")].nobs), "r2": regm[(y, "all")].rsquared}
    for k, y in (("half_life", "log_half_life"), ("lift", "log_lift")):
        regsum[k].update({"age": term(y, "deaths", "age_at_event"), "deaths_n": int(regm[(y, "deaths")].nobs),
                          "deaths_r2": regm[(y, "deaths")].rsquared})

    # ---- group tables ----
    agg = dict(n=("event_id", "size"), spikes=("spike", "sum"), half_life_median=("half_life", "median"),
               late_share_median=("late_share", "median"), lift_median=("lift", "median"),
               baseline_median=("baseline", "median"), peak_ratio_median=("peak_ratio", "median"))
    sp = m.assign(peak_ratio=m.peak_ratio.where(m.spike), half_life=m.half_life.where(m.spike))
    occ = sp.groupby(["event_type", "occupation_group"]).agg(**agg).reset_index()
    occ.to_csv(TAB / "by_occupation.csv", index=False, float_format="%.4g")
    fam = (sp.assign(group=np.where(sp.event_type == "death", "Death", sp.award_family))
             .groupby("group").agg(**agg, share_spike=("spike", "mean"), spec_lift_median=("spec_lift", "median"),
                                   spec_baseline_median=("spec_baseline", "median")).reset_index())
    fam.to_csv(TAB / "by_event_group.csv", index=False, float_format="%.4g")

    # ---- sensitivity rows ----
    sens = []
    for t, g in [("all", m), ("death", m[m.event_type == "death"]), ("award", m[m.event_type == "award"])]:
        spk = g[g.spike]
        sens += [
            {"sample": t, "measure": "half-life, smoothed (7 days) against smoothed peak (main)", "median": spk.half_life.median(), "share_one_day": (spk.half_life == 1).mean()},
            {"sample": t, "measure": "half-life, smoothed (3 days) against smoothed peak", "median": spk.half_life_w3.median(), "share_one_day": (spk.half_life_w3 == 1).mean()},
            {"sample": t, "measure": "half-life, smoothed (14 days) against smoothed peak", "median": spk.half_life_w14.median(), "share_one_day": (spk.half_life_w14 == 1).mean()},
            {"sample": t, "measure": "half-life, daily views against daily peak", "median": spk.half_life_raw.median(), "share_one_day": (spk.half_life_raw == 1).mean()},
            {"sample": t, "measure": "half-life, as in the spec (smoothed against daily peak)", "median": spk.half_life_spec.median(), "share_one_day": (spk.half_life_spec == 1).mean()},
            {"sample": t, "measure": "half-life, peak searched over days 0 to 30", "median": g[g.p30_spike].p30_half_life.median(), "share_one_day": (g[g.p30_spike].p30_half_life == 1).mean()},
        ]
    sens = pd.DataFrame(sens)
    sens.to_csv(TAB / "half_life_sensitivity.csv", index=False, float_format="%.4g")
    p30 = {t: {"n_spike": int(g.p30_spike.sum()), "n": len(g), "half_life_median": float(g[g.p30_spike].p30_half_life.median()),
               "peak_ratio_median": float(g[g.p30_spike].p30_peak_ratio.median()),
               "late_share_median": float(g[g.p30_spike].p30_late_share.median()),
               "peak_after_day3": int((g.p30_spike & (g.p30_peak_day > 3)).sum())}
           for t, g in [("death", m[m.event_type == "death"]), ("award", m[m.event_type == "award"])]}
    osc = m[m.preseason_baseline]
    oscar = {"n": len(osc), "baseline_preseason_median": float(osc.baseline.median()),
             "baseline_spec_median": float(osc.spec_baseline.median()),
             "lift_preseason_median": float(osc.lift.median()), "lift_spec_median": float(osc.spec_lift.median()),
             "share_lift_above1": float((osc.lift > 1).mean()),
             "baseline_early_median": float(osc.early_baseline.median()), "lift_early_median": float(osc.early_lift.median()),
             "share_lift_early_above1": float((osc.early_lift > 1).mean())}
    pd.DataFrame([{"baseline": "pre-season (53 days ending 8 days before nominations)", "baseline_median": oscar["baseline_preseason_median"], "lift_median": oscar["lift_preseason_median"]},
                  {"baseline": "spec (days -60 to -8 before the ceremony)", "baseline_median": oscar["baseline_spec_median"], "lift_median": oscar["lift_spec_median"]},
                  {"baseline": "days -150 to -90 before the ceremony", "baseline_median": oscar["baseline_early_median"], "lift_median": oscar["lift_early_median"]}]
                 ).to_csv(TAB / "oscar_baseline.csv", index=False, float_format="%.4g")
    bot = {
        "events_with_capped_day": int((m.capped_days > 0).sum()), "capped_days_total": int(m.capped_days.sum()),
        "half_life_changed": int(((m.half_life != m.half_life_capped) & m.spike & m.half_life.notna()).sum()),
        "lift_median_capped": {t: float(m[m.event_type == t].lift_capped.median()) for t in ("death", "award")},
    }

    summary = {"counts": counts, "dropped_dates": dd, "eda": eda, "model_wins": wins.to_dict("records"), "models": models,
               "avg_curve": avg, "regressions": regsum, "half_life_sensitivity": sens.to_dict("records"),
               "peak_0_30": p30, "oscar_baseline": oscar, "bot_check": bot,
               "last_data_day": "2026-10-27", "last_data_day_text": "27 October 2026"}
    (RES / "summary.json").write_text(json.dumps(summary, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)) + "\n")
    print(json.dumps({"analyzed": counts["analyzed"], "kinds": counts["spike_kinds"], "wins": wins.to_dict("records"),
                      "models": {k: v for k, v in models.items() if k != "recovery"},
                      "hl": {t: (eda[t]["half_life_median"], eda[t]["half_life_raw_median"], eda[t]["half_life_spec_median"]) for t in ("death", "award")},
                      "lift": {k: (eda[k]["lift_median"], eda[k]["spec_lift_median"]) for k in eda}, "oscar": oscar, "p30": p30,
                      "reg_award": {k: (v["award"]["coef"], v["award"]["p"]) for k, v in regsum.items()}}, indent=1, default=str))


if __name__ == "__main__":
    main()
