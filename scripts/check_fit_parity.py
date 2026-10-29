"""Check that assets/fit.js (the browser) and scripts/fits.py give the same answers.

Runs both on a sample of stored series (node is required), including every Academy Award
event with its pre-season baseline window, and compares baseline, peak day, spike class,
both half-lives, after-week-one share, lift, the winning model and each model's AIC.
Exits non-zero on any mismatch.
"""
import json, math, pathlib, subprocess, sys
import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import fits
import analyze

ROOT = pathlib.Path(__file__).resolve().parent.parent
JS = """
const F = require(process.argv[1]);
const cases = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const nn = x => (x === undefined || x !== x) ? null : x;
const out = cases.map(c => {
  const v = c.v.map(x => x === null ? NaN : x);
  const base = c.base ? {v: c.base.v.map(x => x === null ? NaN : x), wd0: c.base.wd0} : null;
  const r = F.measures(v, c.wd0, 7, base);
  const f = r.m.spike ? F.fitAll(r.adjusted, r.m.baseline, r.m.peakDay) : null;
  return {baseline: r.m.baseline, peak_day: r.m.peakDay, kind: r.m.spikeKind, half_life: nn(r.m.halfLife),
          half_life_raw: nn(r.m.halfLifeRaw), late: nn(r.m.lateShare), lift: nn(r.m.lift),
          best: f ? f.best : null, aic: f ? f.aic : null};
});
process.stdout.write(JSON.stringify(out));
"""


def nn(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else x


def close(a, b, tol=1e-9):
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= tol * max(1.0, abs(a))


def main(n=60):
    ev = pd.read_csv(ROOT / "data/events.csv", keep_default_na=False).set_index("event_id")
    s, bases = analyze.load_series()
    ids = list(s.sample(n=min(n, len(s)), random_state=7).index)
    ids += [i for i in bases if i not in ids]
    cases, py = [], []
    for i in ids:
        v = s.loc[i].to_numpy(dtype=float)
        wd0 = analyze.weekday0(ev.loc[i, "event_date"])
        base = bases.get(i)
        m, a, ex = fits.measures(v, wd0, base=base)
        f = fits.fit_all(a, m["baseline"], m["peak_day"]) if m["spike"] else None
        py.append({"baseline": m["baseline"], "peak_day": m["peak_day"], "kind": m["spike_kind"],
                   "half_life": nn(m["half_life"]), "half_life_raw": nn(m["half_life_raw"]),
                   "late": nn(m["late_share"]), "lift": nn(m["lift"]),
                   "best": f["best"] if f else None, "aic": f["aic"] if f else None})
        c = {"v": [None if np.isnan(x) else x for x in v], "wd0": wd0}
        if base is not None:
            c["base"] = {"v": [None if np.isnan(x) else x for x in base[0]], "wd0": base[1]}
        cases.append(c)
    out = subprocess.run(["node", "-e", JS, str(ROOT / "assets/fit.js")], input=json.dumps(cases),
                         capture_output=True, text=True, check=True).stdout
    js = json.loads(out)
    bad, worst = 0, 0.0
    for i, a, b in zip(ids, py, js):
        same = (close(a["baseline"], b["baseline"], 1e-6) and a["peak_day"] == b["peak_day"] and a["kind"] == b["kind"]
                and a["half_life"] == b["half_life"] and a["half_life_raw"] == b["half_life_raw"]
                and close(a["late"], b["late"]) and close(a["lift"], b["lift"]) and a["best"] == b["best"])
        if a["aic"]:
            d = max(abs(a["aic"][k] - b["aic"][k]) for k in a["aic"])
            worst = max(worst, d)
            same = same and d < 0.05
        if not same:
            bad += 1
            print("mismatch", i, a, b)
    print(f"{len(ids)} events compared ({len(bases)} with a pre-season baseline), {bad} mismatches, "
          f"largest AIC difference {worst:.2e}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
