"""Check that assets/fit.js (the browser) and scripts/fits.py give the same answers.

Runs both on a sample of stored series (node is required) and compares baseline,
peak day, half-life, lift, the winning model and each model's AIC.
Exits non-zero on any mismatch.
"""
import datetime as dt, json, math, pathlib, subprocess, sys
import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import fits

ROOT = pathlib.Path(__file__).resolve().parent.parent
JS = """
const F = require(process.argv[1]);
const cases = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const out = cases.map(c => {
  const v = c.v.map(x => x === null ? NaN : x);
  const r = F.measures(v, c.wd0, 7);
  const f = r.m.spike ? F.fitAll(r.excess, r.m.peakDay) : null;
  return {baseline: r.m.baseline, peak_day: r.m.peakDay, half_life: isNaN(r.m.halfLife) ? null : r.m.halfLife,
          lift: isNaN(r.m.lift) ? null : r.m.lift, best: f ? f.best : null, aic: f ? f.aic : null};
});
process.stdout.write(JSON.stringify(out));
"""


def main(n=60):
    ev = pd.read_csv(ROOT / "data/events.csv", keep_default_na=False).set_index("event_id")
    s = pd.read_csv(ROOT / "data/series.csv.gz", index_col="event_id")
    ids = s.sample(n=min(n, len(s)), random_state=7).index
    cases, py = [], []
    for i in ids:
        v = s.loc[i].to_numpy(dtype=float)
        wd0 = (dt.date.fromisoformat(ev.loc[i, "event_date"]) - dt.timedelta(days=60)).weekday()
        m, a, ex = fits.measures(v, wd0)
        f = fits.fit_all(ex, m["peak_day"]) if m["spike"] else None
        py.append({"baseline": m["baseline"], "peak_day": m["peak_day"],
                   "half_life": None if np.isnan(m["half_life"]) else m["half_life"],
                   "lift": None if np.isnan(m["lift"]) else m["lift"], "best": f["best"] if f else None,
                   "aic": f["aic"] if f else None})
        cases.append({"v": [None if np.isnan(x) else x for x in v], "wd0": wd0})
    out = subprocess.run(["node", "-e", JS, str(ROOT / "assets/fit.js")], input=json.dumps(cases),
                         capture_output=True, text=True, check=True).stdout
    js = json.loads(out)
    bad = 0
    worst = 0.0
    for i, a, b in zip(ids, py, js):
        same = (abs(a["baseline"] - b["baseline"]) < 1e-6 * max(1, a["baseline"]) and a["peak_day"] == b["peak_day"]
                and a["half_life"] == b["half_life"] and a["best"] == b["best"]
                and ((a["lift"] is None and b["lift"] is None) or abs(a["lift"] - b["lift"]) < 1e-9 * max(1, a["lift"])))
        if a["aic"]:
            d = max(abs(a["aic"][k] - b["aic"][k]) for k in a["aic"])
            worst = max(worst, d)
            same = same and d < 0.05
        if not same:
            bad += 1
            print("mismatch", i, a, b)
    print(f"{len(ids)} events compared, {bad} mismatches, largest AIC difference {worst:.2e}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
