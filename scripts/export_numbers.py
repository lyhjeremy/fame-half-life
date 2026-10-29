"""Write every number the page, write-up and README quote into site/numbers.json.

The copy never types a result by hand; it uses {{key}} placeholders filled from this
file by build_site.py, so a rerun of the analysis updates every page together.
"""
import json, pathlib
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
RES, TAB = ROOT / "results", ROOT / "tables"


def pct(x, d=0):
    return f"{100 * x:.{d}f}"


def x2(v):
    return f"{v:.2f}"


def comma(n):
    return f"{int(n):,}"


def days(v):
    v = int(round(v))
    return f"{v} day" if v == 1 else f"{v} days"


def build():
    s = json.loads((RES / "summary.json").read_text())
    c, e, a, w = s["counts"], s["eda"], s["aic"], {r["sample"]: r for r in s["model_wins"]}
    av, rg, bot = s["avg_curve"], s["regressions"], s["bot_check"]
    sm = {r["sample"]: r for r in s["smoothing"]}
    m = pd.read_csv(RES / "measures.csv")
    fam = pd.read_csv(TAB / "by_event_group.csv").set_index("group")
    occ = pd.read_csv(TAB / "by_occupation.csv")
    occ_d = occ[(occ.event_type == "death") & (occ.n >= 15)].set_index("occupation_group")

    excl = {(r["event_type"], r["excluded_reason"]): r["n"] for r in c["excluded"]}
    drops = {}
    for r in c["fetch_drops"]:
        drops[r["drop_reason"]] = drops.get(r["drop_reason"], 0) + r["n"]
    d, aw = e["death"], e["award"]
    sp_d = m[(m.event_type == "death") & m.spike]
    sp_a = m[(m.event_type == "award") & m.spike]

    n = {
        "nDeathCand": comma(c["candidates"]["death"]), "nAwardCand": comma(c["candidates"]["award"]),
        "nDeaths": comma(c["analyzed"]["death"]), "nAwards": comma(c["analyzed"].get("award", 0)),
        "nEvents": comma(c["analyzed"]["death"] + c["analyzed"].get("award", 0)),
        "nCreatedDeath": excl.get(("death", "article created less than 30 days before the event"), 0),
        "nCreatedAward": excl.get(("award", "article created less than 30 days before the event"), 0),
        "nAwardDied": excl.get(("award", "died within a year of the award"), 0),
        "nRenamed": drops.get("article renamed inside the window", 0),
        "nNoData": drops.get("no pageview data", 0) + drops.get("no English article at fetch time", 0),
        "nNoBase": sum(c["no_baseline"].values()),
        "nNobel": c["analyzed_awards"].get("Nobel Prize", 0), "nOscar": c["analyzed_awards"].get("Academy Award", 0),
        "nBallon": c["analyzed_awards"].get("Ballon d'Or", 0), "nBooker": c["analyzed_awards"].get("Booker Prize", 0),
        "nDropDates": 6 + 33,
        # spikes
        "deathNoSpike": pct(d["share_no_spike"], 1), "awardNoSpike": pct(aw["share_no_spike"], 0),
        "deathSpikes": comma(d["n_spike"]), "awardSpikes": comma(aw["n_spike"]),
        "deathPeakX": f"{d['peak_ratio_median']:.0f}", "awardPeakX": f"{aw['peak_ratio_median']:.0f}",
        "deathPeakXlo": f"{d['peak_ratio_p25']:.0f}", "deathPeakXhi": f"{d['peak_ratio_p75']:.0f}",
        "deathBase": comma(round(d["baseline_median"])), "awardBase": comma(round(aw["baseline_median"])),
        "deathPeakDay1": pct(d["peak_day_shares"].get("1", 0)), "deathPeakDay0": pct(d["peak_day_shares"].get("0", 0)),
        # half-life, spec definition
        "deathHalfLife": f"{d['half_life_median']:.0f}", "awardHalfLife": f"{aw['half_life_median']:.0f}",
        "deathHalfPhrase": "within " + days(d["half_life_median"]),
        "deathHalfOne": pct((sp_d.half_life == 1).mean()), "awardHalfOne": pct((sp_a.half_life == 1).mean()),
        "deathHalfMean": f"{d['half_life_mean']:.1f}", "awardHalfMean": f"{aw['half_life_mean']:.1f}",
        "deathHalfOverWeek": pct((sp_d.half_life > 7).mean(), 1),
        "halfW3": f"{sm['all']['w3']:.0f}", "halfW7": f"{sm['all']['w7']:.0f}", "halfW14": f"{sm['all']['w14']:.0f}",
        "deathCumHalf": f"{d['cum_half_median']:.0f}", "awardCumHalf": f"{aw['cum_half_median']:.0f}",
        "deathLate": pct(d["late_share_median"]), "awardLate": pct(aw["late_share_median"]),
        "deathLateLo": pct(d["late_share_p25"]), "deathLateHi": pct(d["late_share_p75"]),
        # lift
        "deathLift": x2(d["lift_median"]), "awardLift": x2(aw["lift_median"]),
        "deathLiftLo": x2(d["lift_p25"]), "deathLiftHi": x2(d["lift_p75"]),
        "awardLiftLo": x2(aw["lift_p25"]), "awardLiftHi": x2(aw["lift_p75"]),
        "deathLiftAbove1": pct(d["lift_share_above1"]), "awardLiftAbove1": pct(aw["lift_share_above1"]),
        "deathLiftAbove2": pct(d["lift_share_above2"]),
        "deathLiftN": comma(d["lift_n"]), "awardLiftN": comma(aw["lift_n"]),
        # averaged curve
        "avgDeathPeak": f"{av['death']['peak_multiple']:.0f}", "avgAwardPeak": f"{av['award']['peak_multiple']:.0f}",
        "avgDeathHalf": days(av["death"]["half_day"]), "avgAwardHalf": days(av["award"]["half_day"]),
        "avgDeathTenth": days(av["death"]["tenth_day"]), "avgAwardTenth": days(av["award"]["tenth_day"]),
        "avgDeath30": x2(av["death"]["day30"]), "avgAward30": x2(av["award"]["day30"]),
        "avgDeath90": x2(av["death"]["day90"]), "avgAward90": x2(av["award"]["day90"]),
        "avgDeathEnd": x2(av["death"]["end_month"]), "avgAwardEnd": x2(av["award"]["end_month"]),
        # models
        "nFitted": comma(a["n_fitted"]), "nFittedDeath": comma(w["death"]["n"]), "nFittedAward": comma(w["award"]["n"]),
        "winBiAll": pct(w["all"]["biexp"]), "winPowAll": pct(w["all"]["pow"]), "winExpAll": pct(w["all"]["exp"]),
        "winBiDeath": pct(w["death"]["biexp"]), "winPowDeath": pct(w["death"]["pow"]), "winExpDeath": pct(w["death"]["exp"]),
        "winBiAward": pct(w["award"]["biexp"]), "winPowAward": pct(w["award"]["pow"]), "winExpAward": pct(w["award"]["exp"]),
        "dAicBiPow": f"{-a['biexp_minus_pow_median']:.0f}", "dAicBiExp": f"{-a['biexp_minus_exp_median']:.0f}",
        "shareBiBy10": pct(a["share_biexp_beats_pow_by_10"]), "sharePowBeatsExp": pct(a["share_pow_beats_exp"]),
        "tau1": f"{a['bi_tau1_median']:.1f}", "tau2": f"{a['bi_tau2_median']:.0f}",
        "tau1Death": f"{a['bi_tau1_median_death']:.1f}", "tau2Death": f"{a['bi_tau2_median_death']:.0f}",
        "tau1Award": f"{a['bi_tau1_median_award']:.1f}", "tau2Award": f"{a['bi_tau2_median_award']:.0f}",
        "biW": pct(a["bi_w_median"], 1), "powAlpha": f"{a['pow_alpha_median']:.2f}",
        "fitDays": f"{a['fit_n_median']:.0f}", "nSpikeNotFitted": a["n_spike_not_fitted"],
        # checks
        "dowAmp": f"{e['all']['dow_amplitude_median']:.2f}",
        "botEvents": bot["events_with_capped_day"], "botDays": bot["capped_days_total"],
        "botHalfChanged": bot["half_life_changed"],
        "botLiftDeath": x2(bot["lift_median_capped"]["death"]), "botLiftAward": x2(bot["lift_median_capped"]["award"]),
        "lastDay": "27 October 2026",
    }
    # regressions: coefficients on log outcomes, shown as percentage changes
    def eff(t):
        return None if t is None else (100 * (2.718281828459045 ** t["coef"] - 1), t["p"])
    for k in ("half_life", "lift"):
        r = rg[k]
        aw_e, base_e = eff(r["award"]), eff(r["log_baseline"])
        n[f"reg_{k}_n"] = comma(r["n"]); n[f"reg_{k}_r2"] = f"{r['r2']:.2f}"
        n[f"reg_{k}_award"] = f"{aw_e[0]:+.0f}"; n[f"reg_{k}_award_p"] = f"{aw_e[1]:.3f}"
        n[f"reg_{k}_base"] = f"{base_e[0]:+.0f}"; n[f"reg_{k}_base_p"] = f"{base_e[1]:.3f}"
        ag = eff(r["age"])
        n[f"reg_{k}_age"] = f"{ag[0]:+.1f}"; n[f"reg_{k}_age_p"] = f"{ag[1]:.3f}"
        n[f"reg_{k}_dn"] = comma(r["deaths_n"]); n[f"reg_{k}_dr2"] = f"{r['deaths_r2']:.2f}"
        yr = eff(r["year"])
        n[f"reg_{k}_year"] = f"{yr[0]:+.1f}"; n[f"reg_{k}_year_p"] = f"{yr[1]:.3f}"
    # groups, for copy: highest and lowest late share and lift among occupations with n >= 15
    if len(occ_d):
        hi, lo = occ_d.late_share_median.idxmax(), occ_d.late_share_median.idxmin()
        n.update({"occLateHi": hi, "occLateHiV": pct(occ_d.loc[hi, "late_share_median"]),
                  "occLateLo": lo, "occLateLoV": pct(occ_d.loc[lo, "late_share_median"])})
        hi, lo = occ_d.lift_median.idxmax(), occ_d.lift_median.idxmin()
        n.update({"occLiftHi": hi, "occLiftHiV": x2(occ_d.loc[hi, "lift_median"]),
                  "occLiftLo": lo, "occLiftLoV": x2(occ_d.loc[lo, "lift_median"])})
    for g, key in (("Nobel Prize", "nobel"), ("Academy Award", "oscar"), ("Ballon d'Or", "ballon"), ("Booker Prize", "booker"), ("Death", "death")):
        if g in fam.index:
            r = fam.loc[g]
            n[f"{key}Lift"] = x2(r.lift_median); n[f"{key}PeakX"] = f"{r.peak_ratio_median:.0f}"
            n[f"{key}Late"] = pct(r.late_share_median); n[f"{key}Base"] = comma(round(r.baseline_median))
            n[f"{key}N"] = int(r.n)
    rows = []
    for g in ("Death", "Nobel Prize", "Academy Award", "Ballon d'Or", "Booker Prize"):
        if g in fam.index:
            r = fam.loc[g]
            rows.append(f'<tr><td>{g}</td><td class="num">{int(r.n):,}</td><td class="num">{round(r.baseline_median):,}</td>'
                        f'<td class="num">{r.peak_ratio_median:.0f}x</td><td class="num">{r.half_life_median:.0f}</td>'
                        f'<td class="num">{100 * r.late_share_median:.0f}%</td><td class="num">{r.lift_median:.2f}x</td></tr>')
    n["groupRows"] = "\n".join(rows)
    (ROOT / "site/numbers.json").write_text(json.dumps(n, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(n)} numbers written")


if __name__ == "__main__":
    build()
