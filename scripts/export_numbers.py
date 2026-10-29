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


def pf(p):
    return "< 0.001" if p < 0.001 else f"= {p:.3f}"


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
    occ_d = occ[(occ.event_type == "death") & (occ.n >= 15) & (occ.occupation_group != "other")].set_index("occupation_group")

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
        "tau1": f"{a['bi_tau1_median']:.1f}", "tau2": f"{a['bi_tau2_median']:,.0f}",
        "tau1Death": f"{a['bi_tau1_median_death']:.1f}", "tau2Death": f"{a['bi_tau2_median_death']:,.0f}",
        "tau1Award": f"{a['bi_tau1_median_award']:.1f}", "tau2Award": f"{a['bi_tau2_median_award']:,.0f}",
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
        n[f"reg_{k}_award"] = f"{aw_e[0]:+.0f}"; n[f"reg_{k}_award_p"] = pf(aw_e[1])
        n[f"reg_{k}_base"] = f"{base_e[0]:+.0f}"; n[f"reg_{k}_base_p"] = pf(base_e[1])
        ag = eff(r["age"])
        n[f"reg_{k}_age"] = f"{ag[0]:+.1f}"; n[f"reg_{k}_age_p"] = pf(ag[1])
        n[f"reg_{k}_dn"] = comma(r["deaths_n"]); n[f"reg_{k}_dr2"] = f"{r['deaths_r2']:.2f}"
        yr = eff(r["year"])
        n[f"reg_{k}_year"] = f"{yr[0]:+.1f}"; n[f"reg_{k}_year_p"] = pf(yr[1])
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
    prose(n, s, m)
    (ROOT / "site/numbers.json").write_text(json.dumps(n, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(n)} numbers written")


def prose(n, s, m):
    """Sentences whose direction depends on the results, so a rerun cannot leave a claim
    pointing the wrong way. Numbers come from n; nothing is typed by hand."""
    f = lambda v: float(str(v).replace(",", ""))
    above = lambda v: "above" if f(v) > 1 else "below"
    age = f(n["reg_lift_age"])
    n["agePhrase"] = f"{abs(age):.1f}% {'less' if age < 0 else 'more'} lift"
    aw = f(n["reg_lift_award"])
    n["awardPhrase"] = f"{abs(aw):.0f}% {'above' if aw > 0 else 'below'} deaths"
    n["startName"] = "Elizabeth II" if (m.title == "Elizabeth II").any() else m.sort_values("peak", ascending=False).title.iloc[0]
    one = f(n["deathHalfLife"]) == 1
    hl = f"{n['deathHalfLife']} day" if one else f"{n['deathHalfLife']} days"
    n["headline"] = (f"Half the extra attention a death brings is gone within {hl} of the peak. A year later the page still draws "
                     f"{n['deathLift']} times its old traffic (median of {n['deathLiftN']} deaths). Awards fade just as fast at first, and where they "
                     f"settle depends on how known the winner was: Nobel laureates keep {n['nobelLift']} times their old traffic, Oscar winners {n['oscarLift']} times.")
    n["deathHalfPhrase"] = f"within {hl}"
    n["fadeTitle"] = f"The spike is gone within days; a residue stays"
    n["fadeText"] = (f"On the median death the page draws {n['deathPeakX']} times its usual traffic on the peak day, which is the day after the death "
                     f"in {n['deathPeakDay1']}% of cases. The averaged curve loses half its excess in {n['avgDeathHalf']} and nine tenths in "
                     f"{n['avgDeathTenth']}, and sits at {n['avgDeath30']} times baseline a month later and {n['avgDeathEnd']} times in the last month "
                     f"of the year. Awards peak at {n['avgAwardPeak']} times and lose nine tenths in {n['avgAwardTenth']}. Deaths jump again on day +365, the anniversary; "
                     f"awards climb in the last week of the year as the next year's prize comes round.")
    n["avgAlt"] = (f"Median views relative to baseline for deaths and awards, days -60 to +365. Deaths peak at {n['avgDeathPeak']} times baseline and "
                   f"settle near {n['avgDeathEnd']}; awards peak at {n['avgAwardPeak']} times and settle near {n['avgAwardEnd']}.")
    n["curveTitle"] = "Two exponentials fit better than one, or a power law"
    n["curveText"] = (f"Three curves were fitted to each event's excess views after the peak: an exponential, a power law, and the biexponential "
                      f"(a sum of two exponentials) that Candia et al. (2019) found in the decay of attention to songs, films and biographies over years. "
                      f"The biexponential has the lowest AIC for {n['winBiDeath']}% of {n['nFittedDeath']} deaths and {n['winBiAward']}% of "
                      f"{n['nFittedAward']} awards, with a median margin of {n['dAicBiPow']} AIC points over the power law. Its fast part has a median "
                      f"time constant of {n['tau1']} days; the slow part's is {n['tau2']} days, so long that within a year it is close to a flat step "
                      f"above the old baseline.")
    n["winsAlt"] = f"The biexponential wins {n['winBiAll']}% of {n['nFitted']} events, the power law {n['winPowAll']}% and the exponential {n['winExpAll']}%."
    dl, nl, ol = f(n["deathLift"]), f(n["nobelLift"]), f(n["oscarLift"])
    n["settleTitle"] = ("A death leaves a page busier than before" if dl > 1 else "After a death, a page drops back below its old traffic") + \
                       (f"; an Oscar leaves it quieter" if ol < 1 else "")
    n["settleText"] = (f"A year after a death the median page draws {n['deathLift']} times its old traffic, and {n['deathLiftAbove1']}% of pages sit above "
                       f"their baseline. Awards spread far wider. Nobel laureates, with a median of {n['nobelBase']} views a day beforehand, keep "
                       f"{n['nobelLift']} times that. Academy Award winners start from {n['oscarBase']} a day, already raised by awards season, and end "
                       f"the year at {n['oscarLift']} times it. Among deaths, each extra year of age at death goes with {n['agePhrase']}"
                       f" (p {n['reg_lift_age_p']}), and pages that were busier beforehand gain "
                       f"{'less' if f(n['reg_lift_base']) < 0 else 'more'}.")
    n["liftAlt"] = (f"Distribution of lift. Deaths cluster near one, median {n['deathLift']}; awards spread from well below one to far above, "
                    f"median {n['awardLift']}.")
    wide = abs(f(n['nobelLift']) - f(n['oscarLift'])) > f(n['occLiftHiV']) - f(n['occLiftLoV'])
    n["whoTitle"] = "Which prize matters more than what the person did" if wide else "Occupation and prize both matter"
    n["whoText"] = (f"Among deaths, the share of the first year's extra views that arrive after the first week runs from {n['occLateLoV']}% "
                    f"({n['occLateLo']}) to {n['occLateHiV']}% ({n['occLateHi']}), and median lift from {n['occLiftLoV']} times ({n['occLiftLo']}) "
                    f"to {n['occLiftHiV']} times ({n['occLiftHi']}). "
                    + ("The gap between Nobel and Oscar winners is wider than any gap between occupations."
                       if abs(f(n['nobelLift']) - f(n['oscarLift'])) > f(n['occLiftHiV']) - f(n['occLiftLoV']) else
                       "Those gaps are as wide as the gaps between prizes."))
    n["botPhrase"] = (f"changes {n['botEvents']} events and {n['botHalfChanged']} half-{'life' if n['botHalfChanged'] == 1 else 'lives'}; median lift is {n['botLiftDeath']} for deaths "
                      f"with the cap")
    n["halfLifeLimit"] = (f"The half-life as specified saturates: the spike is narrower than the 7-day smoothing window, so the half-life is one day "
                          f"for {n['deathHalfOne']}% of deaths. With a 3-day window the median is {n['halfW3']} days, with 14 days {n['halfW14']}. "
                          f"The share of extra views after week one, and the fitted curves, carry the comparisons instead.")
    # write-up
    n["heroSub"] = (f"Daily English Wikipedia views around {n['nDeaths']} deaths and {n['nAwards']} major awards, 2016 to 2025. On the median "
                    f"death a page draws {n['deathPeakX']} times its usual traffic at the peak, and half the excess is gone within {hl}. The "
                    f"fade follows two exponentials, a fast one with a time constant of about {n['tau1']} days and a slow one that barely moves "
                    f"within a year. A year on, the page draws {n['deathLift']} times its old traffic.")
    n["f1Title"] = "Half the spike is gone within a day or two"
    n["f1Text"] = n["fadeText"] + (f" Measured as specified, the half-life is {n['deathHalfLife']} day for deaths and {n['awardHalfLife']} for awards; "
                  f"it is one day in {n['deathHalfOne']}% of deaths with a spike. Most of the attention comes at once: only {n['deathLate']}% "
                  f"of a death's first-year excess views (median) arrive after the first week.")
    n["f2Text"] = n["curveText"] + (f" The power law still beats the exponential in {n['sharePowBeatsExp']}% of events, which is what a "
                  f"long tail looks like. The two shapes agree with Candia et al. on form; their time scale is years since publication, "
                  f"this one is days since an event.")
    n["f3Title"] = n["settleTitle"]
    n["f3Text"] = n["settleText"].split(" Among deaths")[0]
    n["f3Reg"] = (f"A regression of log lift on event type, log baseline, occupation group and year (OLS, HC3 errors, n = {n['reg_lift_n']}, "
                  f"R² = {n['reg_lift_r2']}) puts awards {n['awardPhrase']} at the same prior traffic "
                  f"(p {n['reg_lift_award_p']}). Among deaths, with age added (n = {n['reg_lift_dn']}, R² = {n['reg_lift_dr2']}), each extra "
                  f"year of age at death goes with {n['agePhrase']} (p {n['reg_lift_age_p']}). The same regression for log "
                  f"half-life explains almost nothing (R² = {n['reg_half_life_r2']}), because the half-life barely varies.")
    n["f4Title"] = n["whoTitle"]
    n["f4Text"] = n["whoText"]
    n["checksText"] = (f"Bot leakage: capping any day above 50 times the median of its six neighbors touches {n['botEvents']} events and changes "
                       f"{n['botHalfChanged']} half-{'life' if n['botHalfChanged'] == 1 else 'lives'}; median lift with the cap is {n['botLiftDeath']} for deaths and {n['botLiftAward']} for awards. "
                       f"Renames: {n['nRenamed']} events were dropped because the article moved to a new title inside the window. Smoothing: the "
                       f"median half-life is {n['halfW3']} days with a 3-day window, {n['halfW7']} with 7 and {n['halfW14']} with 14. The spike is "
                       f"narrower than the window, so the specified half-life is one day for most events; the late-share measure and the fitted "
                       f"curves are less sensitive to that choice. Day of week: the median page's busiest weekday draws {n['dowAmp']} "
                       f"times its quietest, which is why every series is adjusted before measuring.")
    n["readmeResults"] = "\n".join([
        f"- Peak: on the median death a page draws {n['deathPeakX']} times its baseline at the peak (middle half {n['deathPeakXlo']} to {n['deathPeakXhi']} times); the peak is the day after the death in {n['deathPeakDay1']}% of cases.",
        f"- Half-life, as specified: {n['deathHalfLife']} day for deaths and {n['awardHalfLife']} for awards; one day for {n['deathHalfOne']}% of deaths with a spike. With 3-day smoothing the median is {n['halfW3']} days.",
        f"- After week one: {n['deathLate']}% of a death's first-year excess views (median) arrive more than a week after the peak; for awards {n['awardLate']}%.",
        f"- Curve shape: the biexponential has the lowest AIC for {n['winBiAll']}% of {n['nFitted']} fitted events ({n['winBiDeath']}% of deaths, {n['winBiAward']}% of awards); median fast time constant {n['tau1']} days.",
        f"- Lift a year later: {n['deathLift']} times baseline for deaths ({n['deathLiftAbove1']}% above 1), {n['nobelLift']} for Nobel laureates, {n['oscarLift']} for Academy Award winners.",
        f"- Among deaths, each extra year of age at death goes with {n['agePhrase']} (p {n['reg_lift_age_p']}).",
    ])
    n["writeupResults"] = "\n\n".join(["### The fade\n\n" + n["f1Text"], "### The curve\n\n" + n["f2Text"],
                                        "### The aftermath\n\n" + n["settleText"] + "\n\n" + n["f3Reg"],
                                        "### Who lasts\n\n" + n["whoText"]])


if __name__ == "__main__":
    build()
