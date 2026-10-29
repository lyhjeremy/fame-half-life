"""Write every number the page, write-up and README quote into site/numbers.json.

The copy never types a result by hand; it uses {{key}} placeholders filled from this
file by build_site.py, so a rerun of the analysis updates every page together. Sentences
whose direction depends on a result are generated here, so a rerun cannot leave a claim
pointing the wrong way.
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
    return f"{int(round(n)):,}"


def days(v):
    v = int(round(v))
    return f"{v} day" if v == 1 else f"{v} days"


def build():
    s = json.loads((RES / "summary.json").read_text())
    c, e, md = s["counts"], s["eda"], s["models"]
    w = {r["sample"]: r for r in s["model_wins"]}
    av, rg, bot, osc, p30 = s["avg_curve"], s["regressions"], s["bot_check"], s["oscar_baseline"], s["peak_0_30"]
    sens = pd.DataFrame(s["half_life_sensitivity"])
    rec = pd.DataFrame(md["recovery"])
    fam = pd.read_csv(TAB / "by_event_group.csv").set_index("group")
    occ = pd.read_csv(TAB / "by_occupation.csv")
    occ_d = occ[(occ.event_type == "death") & (occ.n >= 15) & (occ.occupation_group != "other")].set_index("occupation_group")
    excl = {(r["event_type"], r["excluded_reason"]): r["n"] for r in c["excluded"]}
    drops = {}
    for r in c["fetch_drops"]:
        drops[r["drop_reason"]] = drops.get(r["drop_reason"], 0) + r["n"]
    d, aw = e["death"], e["award"]
    n = {
        "nDeathCand": comma(c["candidates"]["death"]), "nAwardCand": comma(c["candidates"]["award"]),
        "nDeaths": comma(c["analyzed"]["death"]), "nAwards": comma(c["analyzed"]["award"]),
        "nEvents": comma(c["analyzed"]["death"] + c["analyzed"]["award"]),
        "nCreatedDeath": excl.get(("death", "article created less than 30 days before the event"), 0),
        "nCreatedAward": excl.get(("award", "article created less than 30 days before the event"), 0),
        "nAwardDied": excl.get(("award", "died within a year of the award"), 0),
        "nRenamed": drops.get("article renamed inside the window", 0),
        "nLaterTitle": c["title_from_later_move"], "nAmended": c["amended_rows"],
        "nNoBase": sum(c["no_baseline"].values()),
        "nNobel": c["analyzed_awards"].get("Nobel Prize", 0), "nOscar": c["analyzed_awards"].get("Academy Award", 0),
        "nBallon": c["analyzed_awards"].get("Ballon d'Or", 0), "nBooker": c["analyzed_awards"].get("Booker Prize", 0),
        "nDropDates": sum(s["dropped_dates"].values()),
        "lastDay": s["last_data_day_text"],
        # spike classes
        "deathSpikes": comma(d["n_spike"]), "deathDelayed": d["n_delayed"], "deathNone": d["n_none"],
        "awardSpikes": comma(aw["n_spike"]), "awardDelayed": aw["n_delayed"], "awardNone": aw["n_none"],
        "deathDelayedPct": pct(d["n_delayed"] / d["n"], 1),
        "p30DeathLate": p30["death"]["peak_after_day3"], "p30DeathHalf": f"{p30['death']['half_life_median']:.0f}",
        "p30AwardHalf": f"{p30['award']['half_life_median']:.0f}",
        # peak
        "deathPeakX": f"{d['peak_ratio_median']:.0f}", "awardPeakX": f"{aw['peak_ratio_median']:.0f}",
        "deathPeakXlo": f"{d['peak_ratio_p25']:.0f}", "deathPeakXhi": f"{d['peak_ratio_p75']:.0f}",
        "deathBase": comma(d["baseline_median"]), "awardBase": comma(aw["baseline_median"]),
        "deathPeakDay1": pct(d["peak_day_shares"].get("1", 0)), "deathPeakDay0": pct(d["peak_day_shares"].get("0", 0)),
        # half-life
        "deathHalfLife": f"{d['half_life_median']:.0f}", "deathHalfDays": days(d["half_life_median"]), "awardHalfLife": f"{aw['half_life_median']:.0f}",
        "deathHalfLo": f"{d['half_life_p25']:.0f}", "deathHalfHi": f"{d['half_life_p75']:.0f}",
        "deathHalfOne": pct(d["half_life_share1"]), "awardHalfOne": pct(aw["half_life_share1"]),
        "deathHalfRaw": f"{d['half_life_raw_median']:.0f}", "deathHalfSpec": f"{d['half_life_spec_median']:.0f}",
        "deathHalfSpecOne": pct(d["half_life_spec_share1"]), "deathHalfRawOne": pct(d["half_life_raw_share1"]),
        "deathLate": pct(d["late_share_median"]), "awardLate": pct(aw["late_share_median"]),
        "dowAmp": f"{e['all']['dow_amplitude_median']:.2f}",
        # lift
        "deathLift": x2(d["lift_median"]), "awardLift": x2(aw["lift_median"]),
        "deathLiftLo": x2(d["lift_p25"]), "deathLiftHi": x2(d["lift_p75"]),
        "deathLiftAbove1": pct(d["lift_share_above1"]), "awardLiftAbove1": pct(aw["lift_share_above1"]),
        "deathLiftN": comma(d["lift_n"]),
        "oscarBasePre": comma(osc["baseline_preseason_median"]), "oscarBaseSpec": comma(osc["baseline_spec_median"]),
        "oscarBaseEarly": comma(osc["baseline_early_median"]),
        "oscarLiftPre": x2(osc["lift_preseason_median"]), "oscarLiftSpec": x2(osc["lift_spec_median"]),
        "oscarLiftEarly": x2(osc["lift_early_median"]), "oscarAbove1": pct(osc["share_lift_above1"]),
        "oscarEarlyAbove1": pct(osc["share_lift_early_above1"]),
        # averaged curve
        "avgDeathPeak": f"{av['death']['peak_multiple']:.0f}", "avgAwardPeak": f"{av['award']['peak_multiple']:.0f}",
        "avgDeathHalf": days(av["death"]["half_day"]), "avgDeathTenth": days(av["death"]["tenth_day"]),
        "avgAwardTenth": days(av["award"]["tenth_day"]),
        "avgDeath30": x2(av["death"]["day30"]), "avgDeathEnd": x2(av["death"]["end_month"]),
        "avgDeath365": x2(av["death"]["day365"]), "avgAwardEnd": x2(av["award"]["end_month"]),
        # models
        "nFitted": comma(md["n_fitted"]), "nFittedDeath": comma(w["death"]["n"]), "nFittedAward": comma(w["award"]["n"]),
        "marginMedian": f"{md['margin_median']:.0f}", "marginOver10": pct(md["share_margin_over_10"]),
        "tau1": f"{md['bi_tau1_median']:.1f}", "tau2": comma(md["bi_tau2_median"]),
        "slowShare": pct(md["bi_slow_share_median"], 1), "tau2Over365": pct(md["bi_tau2_over_365"]),
        "expTau": f"{md['exp_tau_median']:.1f}", "powAlpha": f"{md['pow_alpha_median']:.2f}",
        # checks
        "botEvents": bot["events_with_capped_day"], "botHalfChanged": bot["half_life_changed"],
        "botLiftDeath": x2(bot["lift_median_capped"]["death"]), "botLiftAward": x2(bot["lift_median_capped"]["award"]),
    }
    for k in ("all", "death", "award"):
        for mdl, lab in (("biexp", "Bi"), ("pow", "Pow"), ("exp", "Exp")):
            n[f"win{lab}{k.capitalize()}"] = pct(w[k][mdl])
            n[f"spec{lab}{k.capitalize()}"] = pct(w[k][f"spec_{mdl}"])
    for sig in (0.15, 0.30):
        r = rec[rec.noise_sigma.round(2) == sig].set_index("truth")
        tag = "Lo" if sig < 0.2 else "Hi"
        for t in ("exp", "pow", "biexp"):
            n[f"rec{t.capitalize()}{tag}"] = pct(r.loc[t, "recovered"])
            n[f"recSpec{t.capitalize()}{tag}"] = pct(r.loc[t, "spec_method_recovered"])
        n[f"recExpAsBi{tag}"] = pct(r.loc["exp", "picked_biexp"])
        n[f"recSpecExpAsBi{tag}"] = pct(r.loc["exp", "spec_method_picked_biexp"])
    for col, key in (("w3", "half-life, smoothed (3 days)"), ("w14", "half-life, smoothed (14 days)")):
        row = sens[(sens["sample"] == "all") & sens.measure.str.startswith(key)].iloc[0]
        n[f"half{col.upper()}"] = f"{row['median']:.0f}"

    def eff(t):
        return 100 * (2.718281828459045 ** t["coef"] - 1), t["p"]
    for k in ("half_life", "lift", "lift_spec"):
        r = rg[k]
        a_, p_ = eff(r["award"])
        n[f"reg_{k}_n"] = comma(r["n"]); n[f"reg_{k}_r2"] = f"{r['r2']:.2f}"
        n[f"reg_{k}_award"] = f"{abs(a_):.0f}% {'above' if a_ > 0 else 'below'}"; n[f"reg_{k}_award_p"] = pf(p_)
        b_, bp = eff(r["log_baseline"])
        n[f"reg_{k}_base_sign"] = "less" if r["log_baseline"]["coef"] < 0 else "more"
    for k in ("half_life", "lift"):
        r = rg[k]
        ag, ap = eff(r["age"])
        n[f"reg_{k}_age"] = f"{abs(ag):.1f}% {'less' if ag < 0 else 'more'}"; n[f"reg_{k}_age_p"] = pf(ap)
        n[f"reg_{k}_dn"] = comma(r["deaths_n"]); n[f"reg_{k}_dr2"] = f"{r['deaths_r2']:.2f}"
    if len(occ_d):
        hi, lo = occ_d.late_share_median.idxmax(), occ_d.late_share_median.idxmin()
        n.update({"occLateHi": hi, "occLateHiV": pct(occ_d.loc[hi, "late_share_median"]),
                  "occLateLo": lo, "occLateLoV": pct(occ_d.loc[lo, "late_share_median"])})
        hi, lo = occ_d.lift_median.idxmax(), occ_d.lift_median.idxmin()
        n.update({"occLiftHi": hi, "occLiftHiV": x2(occ_d.loc[hi, "lift_median"]),
                  "occLiftLo": lo, "occLiftLoV": x2(occ_d.loc[lo, "lift_median"])})
    for g, key in (("Nobel Prize", "nobel"), ("Academy Award", "oscar"), ("Ballon d'Or", "ballon"), ("Booker Prize", "booker"), ("Death", "death")):
        r = fam.loc[g]
        n[f"{key}Lift"] = x2(r.lift_median); n[f"{key}PeakX"] = f"{r.peak_ratio_median:.0f}"
        n[f"{key}Late"] = pct(r.late_share_median); n[f"{key}Base"] = comma(r.baseline_median); n[f"{key}N"] = int(r.n)
    rows = []
    for g in ("Death", "Nobel Prize", "Academy Award", "Ballon d'Or", "Booker Prize"):
        r = fam.loc[g]
        rows.append(f'<tr><td>{g}</td><td class="num">{int(r.n):,}</td><td class="num">{round(r.baseline_median):,}</td>'
                    f'<td class="num">{r.peak_ratio_median:.0f}x</td><td class="num">{r.half_life_median:.0f}</td>'
                    f'<td class="num">{100 * r.late_share_median:.0f}%</td><td class="num">{r.lift_median:.2f}x</td></tr>')
    n["groupRows"] = "\n".join(rows)
    rr = []
    for t, lab in (("exp", "Exponential"), ("pow", "Power law"), ("biexp", "Biexponential")):
        rr.append(f'<tr><td>{lab}</td><td class="num">{n["rec" + t.capitalize() + "Lo"]}%</td><td class="num">{n["rec" + t.capitalize() + "Hi"]}%</td>'
                  f'<td class="num">{n["recSpec" + t.capitalize() + "Lo"]}%</td><td class="num">{n["recSpec" + t.capitalize() + "Hi"]}%</td></tr>')
    n["recoveryRows"] = "\n".join(rr)
    n["simN"] = int(rec.n.iloc[0])
    hr = []
    for meas in sens.measure.unique():
        dr = sens[(sens["sample"] == "death") & (sens.measure == meas)].iloc[0]
        ar = sens[(sens["sample"] == "award") & (sens.measure == meas)].iloc[0]
        hr.append(f'<tr><td>{meas[0].upper() + meas[1:]}</td><td class="num">{dr["median"]:.0f}</td><td class="num">{100 * dr.share_one_day:.0f}%</td>'
                  f'<td class="num">{ar["median"]:.0f}</td><td class="num">{100 * ar.share_one_day:.0f}%</td></tr>')
    n["halfRows"] = "\n".join(hr)
    prose(n, s)
    (ROOT / "site/numbers.json").write_text(json.dumps(n, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(n)} numbers written")


def prose(n, s):
    f = lambda v: float(str(v).replace(",", ""))
    m = pd.read_csv(RES / "measures.csv")
    n["startName"] = "Elizabeth II" if (m.title == "Elizabeth II").any() else m.sort_values("peak", ascending=False).title.iloc[0]
    hl = days(f(n["deathHalfLife"]))
    bi_lead = f(n["winBiAll"]) > 50
    oscar_below = f(n["oscarLiftPre"]) < 1
    n["deathHalfPhrase"] = f"in about {hl}"
    n["headline"] = (f"Half the extra attention a death brings is gone in about {hl}, and nine tenths within {n['avgDeathTenth']}. "
                     f"A year later the median page still draws {n['deathLift']} times its old traffic. Award winners settle higher, "
                     f"a median {n['awardLift']} times, led by Nobel laureates who were barely looked up before ({n['nobelLift']} times).")
    n["fadeTitle"] = "Most of the spike is gone within a week"
    n["fadeText"] = (f"On the median death the page draws {n['deathPeakX']} times its usual traffic on the peak day, which is the day after the death "
                     f"in {n['deathPeakDay1']}% of cases. Smoothed over a week, half the extra traffic is gone {hl} after the peak "
                     f"(middle half {n['deathHalfLo']} to {n['deathHalfHi']} days). The averaged curve loses nine tenths of its excess in "
                     f"{n['avgDeathTenth']} and sits at {n['avgDeath30']} times baseline a month later and {n['avgDeathEnd']} times in the last month "
                     f"of the year, before jumping to {n['avgDeath365']} times on the anniversary. Awards lose nine tenths in {n['avgAwardTenth']}, "
                     f"and climb again in the last week of the year as the next prize comes round.")
    n["avgAlt"] = (f"Median views relative to baseline, days -60 to +365. Deaths peak at {n['avgDeathPeak']} times baseline and settle near "
                   f"{n['avgDeathEnd']}; awards peak at {n['avgAwardPeak']} times and settle near {n['avgAwardEnd']}.")
    n["curveTitle"] = ("A fast fade and a slow tail fit most events" if bi_lead else "No single curve fits most events")
    n["curveText"] = (f"Each event's daily views after the peak were fitted three ways, with every day counted: the baseline plus an exponential "
                      f"decay, plus a power law, or plus a biexponential (two exponentials, the form Candia et al. 2019 found over years in "
                      f"attention to songs, films and biographies). The biexponential has the lowest AIC for {n['winBiDeath']}% of "
                      f"{n['nFittedDeath']} deaths and {n['winBiAward']}% of {n['nFittedAward']} awards; the power law wins {n['winPowDeath']}% "
                      f"of deaths and the exponential {n['winExpDeath']}%. Where the biexponential wins, its fast part has a median time constant "
                      f"of {n['tau1']} days and carries all but {n['slowShare']}% of the initial excess; the slow part's median time constant is "
                      f"{n['tau2']} days. On simulated series the selector names the true model {n['recExpLo']}% of the time for a pure "
                      f"exponential, {n['recPowLo']}% for a power law and {n['recBiexpLo']}% for a biexponential, and it calls "
                      f"{n['recExpAsBiLo']}% of pure exponentials biexponential, so the real share is a mild overstatement.")
    n["winsAlt"] = (f"Share of events won by each model: biexponential {n['winBiAll']}%, power law {n['winPowAll']}%, exponential "
                    f"{n['winExpAll']}% of {n['nFitted']} events.")
    n["settleTitle"] = "A death leaves a page a little busier than before"
    n["settleText"] = (f"A year after a death the median page draws {n['deathLift']} times its old traffic, and {n['deathLiftAbove1']}% of "
                       f"pages sit above their baseline. Award winners settle at a median {n['awardLift']} times, but the prizes differ: Nobel "
                       f"laureates, with a median of {n['nobelBase']} views a day beforehand, keep {n['nobelLift']} times that; Booker winners "
                       f"{n['bookerLift']}; Ballon d'Or winners {n['ballonLift']}. For Academy Award winners the answer depends on which "
                       f"'before' you use: against the 53 days ending a week before the nominations it is {n['oscarLiftPre']}, against "
                       f"days -150 to -90 before the ceremony {n['oscarLiftEarly']}. Among deaths, each extra year of age at death goes with "
                       f"{n['reg_lift_age']} lift (p {n['reg_lift_age_p']}), and pages that were busier beforehand gain {n['reg_lift_base_sign']}.")
    n["liftAlt"] = (f"Distribution of lift. Deaths cluster near one, median {n['deathLift']}; awards spread from below one to far above, "
                    f"median {n['awardLift']}.")
    wide = abs(f(n["nobelLift"]) - f(n["oscarLiftPre"])) > f(n["occLiftHiV"]) - f(n["occLiftLoV"])
    n["whoTitle"] = "Which prize matters more than what the person did" if wide else "Occupation and prize both matter"
    n["whoText"] = (f"Among deaths, the share of the first year's extra views that arrive after the first week runs from {n['occLateLoV']}% "
                    f"({n['occLateLo']}) to {n['occLateHiV']}% ({n['occLateHi']}), and median lift from {n['occLiftLoV']} times "
                    f"({n['occLiftLo']}) to {n['occLiftHiV']} times ({n['occLiftHi']}). "
                    + ("The gap between Nobel and Oscar winners is wider than any gap between occupations." if wide
                       else "Those gaps are as wide as the gaps between prizes."))
    n["botPhrase"] = (f"touches {n['botEvents']} events and " + ("leaves every half-life unchanged" if n["botHalfChanged"] == 0 else
                      f"changes {n['botHalfChanged']} half-{'life' if n['botHalfChanged'] == 1 else 'lives'}"))
    ex_ = [t for t in ("Leonard Cohen", "Sam Shepard", "Steve Ditko") if ((m.title == t) & (m.spike_kind == "delayed")).any()]
    examples = (" (" + ", ".join(ex_[:-1]) + " and " + ex_[-1] + " among them)") if len(ex_) > 1 else ""
    n["spikeText"] = (f"{n['deathSpikes']} of {n['nDeaths']} deaths have a visible spike (peak at least twice the baseline) on days 0 to 3. "
                      f"Another {n['deathDelayed']} ({n['deathDelayedPct']}%) have a delayed spike: nothing on days 0 to 3, then a day above "
                      f"twice the baseline on days 4 to 30{examples}, most often because the death became news days or weeks after it happened. "
                      f"{n['deathNone']} {'death has' if n['deathNone'] == 1 else 'deaths have'} no spike at all.")
    n["heroSub"] = (f"Daily English Wikipedia views around {n['nDeaths']} deaths and {n['nAwards']} major awards, 2016 to 2025. On the "
                    f"median death a page draws {n['deathPeakX']} times its usual traffic at the peak, and half the extra traffic is gone "
                    f"in about {hl}. A year on, the page draws {n['deathLift']} times its old traffic; for award winners the figure is "
                    f"{n['awardLift']}.")
    n["heroTitle"] = (f"Half the spike is gone in about {hl}. " + ("A little of it stays for a year." if f(n["deathLift"]) > 1
                      else "A year later the page is back where it started."))
    n["f1Title"] = "Half the spike is gone in about two days" if f(n["deathHalfLife"]) == 2 else f"Half the spike is gone in about {hl}"
    n["f1Text"] = n["fadeText"] + " " + n["spikeText"]
    n["f2Text"] = n["curveText"] + (f" The model comparison first published on 28 October dropped every day at or below the baseline "
                  f"before fitting; on the same simulations that method called {n['recSpecExpAsBiLo']}% of pure "
                  f"exponentials biexponential, which is why it reported {n['specBiAll']}% biexponential wins.")
    n["f3Title"] = n["settleTitle"]
    n["f3Text"] = n["settleText"].split(" Among deaths")[0]
    n["f3Reg"] = (f"A regression of log lift on event type, log baseline, occupation group and year (OLS, HC3 errors, n = {n['reg_lift_n']}, "
                  f"R² = {n['reg_lift_r2']}) puts awards {n['reg_lift_award']} deaths at the same prior traffic (p {n['reg_lift_award_p']}); "
                  f"with the Oscar baseline as the spec defined it the figure is {n['reg_lift_spec_award']} (p {n['reg_lift_spec_award_p']}). "
                  f"Among deaths, with age added (n = {n['reg_lift_dn']}, R² = {n['reg_lift_dr2']}), each extra year of age at death goes "
                  f"with {n['reg_lift_age']} lift (p {n['reg_lift_age_p']}). The same regression for log half-life explains little "
                  f"(R² = {n['reg_half_life_r2']}).")
    n["f4Title"] = n["whoTitle"]
    n["f4Text"] = n["whoText"]
    n["checksText"] = (f"Bot leakage: capping any day above 50 times the median of its six neighbors {n['botPhrase']}; median lift "
                       f"with the cap is {n['botLiftDeath']} for deaths and {n['botLiftAward']} for awards. Renames: {n['nRenamed']} events "
                       f"were dropped because the article moved to a new title inside the window, and {n['nLaterTitle']} articles moved "
                       f"later are read under the title they had at the time. Peak window: searching for the peak over days 0 to 30 "
                       f"instead of 0 to 3 moves it later for {n['p30DeathLate']} deaths and leaves the median half-life at "
                       f"{n['p30DeathHalf']} days. Smoothing and definition: the table below gives the half-life every way it was "
                       f"measured. Day of week: the median page's busiest weekday draws {n['dowAmp']} times its quietest, which is "
                       f"why every series is adjusted before measuring.")
    n["halfLifeLimit"] = (f"The half-life as the spec first defined it compared a 7-day average with the single peak day, so it came out at "
                          f"one day for {n['deathHalfSpecOne']}% of deaths. It now compares the smoothed series with its own smoothed peak "
                          f"(median {hl}); the old measure stays in the sensitivity table.")
    n["correction"] = (f"Corrected 29 October 2026, after an independent audit. Three 2022 Nobel laureates in economics were missing "
                       f"because the Nobel Prize API gives the wrong year for that prize; they are now in. The curve comparison "
                       f"published on 28 October fitted only days above the baseline, which made a biexponential win almost by default "
                       f"(it reported {n['specBiAll']}%); every day now counts, and the selector was checked on simulated data. The "
                       f"half-life compared a smoothed series with a single raw day; it now compares like with like. {n['deathDelayed']} "
                       f"deaths reported days late are counted as delayed spikes rather than no spike. The Oscar baseline fell after the "
                       f"nominations; it now ends a week before them. Earlier figures are kept as sensitivity rows.")
    n["readmeResults"] = "\n".join([
        f"- Peak: on the median death a page draws {n['deathPeakX']} times its baseline at the peak (middle half {n['deathPeakXlo']} to {n['deathPeakXhi']} times).",
        f"- Half-life: half the extra traffic is gone {hl} after the peak for deaths (median; 7-day smoothing against the smoothed peak) and {days(f(n['awardHalfLife']))} for awards.",
        f"- Spikes: {n['deathSpikes']} deaths spike on days 0 to 3, {n['deathDelayed']} spike later because the news came late, {n['deathNone']} not at all.",
        f"- Curve shape: with every day counted, the biexponential has the lowest AIC for {n['winBiDeath']}% of deaths and {n['winBiAward']}% of awards. In simulation the selector recovers the true model {n['recExpLo']}% (exponential), {n['recPowLo']}% (power law) and {n['recBiexpLo']}% (biexponential) of the time.",
        f"- Lift a year later: {n['deathLift']} times baseline for deaths ({n['deathLiftAbove1']}% above 1), {n['awardLift']} for awards ({n['nobelLift']} for Nobel laureates; {n['oscarLiftPre']} for Academy Award winners against a pre-nomination baseline).",
        f"- Among deaths, each extra year of age at death goes with {n['reg_lift_age']} lift (p {n['reg_lift_age_p']}).",
        f"- Corrected on 29 October 2026 after an audit; see the corrections note in [writeup.md](writeup.md) and entries 26 to 33 of [docs/decisions.md](docs/decisions.md).",
    ])
    n["writeupResults"] = "\n\n".join(["### The fade\n\n" + n["f1Text"], "### The curve\n\n" + n["f2Text"],
                                        "### The aftermath\n\n" + n["settleText"] + "\n\n" + n["f3Reg"],
                                        "### Who lasts\n\n" + n["whoText"]])


if __name__ == "__main__":
    build()
