"""Data for the page: assets/data.json (index, averaged curves, model wins, lift and group
summaries) and assets/series/NN.json (raw daily views per event, 40 shards)."""
import datetime as dt, json, pathlib
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import analyze

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHARDS = 40


def r(x, d=3):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), d)


def main():
    m = pd.read_csv(ROOT / "results/measures.csv", keep_default_na=False, na_values=[""])
    s = pd.read_csv(ROOT / "data/series.csv.gz", index_col="event_id")
    m = m.sort_values(["title", "event_date"]).reset_index(drop=True)
    m["shard"] = [i % SHARDS for i in range(len(m))]
    idx = [[e.event_id, e.title, e.event_type[0], e.award if isinstance(e.award, str) else "", e.event_date,
            e.occupation_group, int(e.shard)] for e in m.itertuples()]
    shards = {k: {} for k in range(SHARDS)}
    bases = analyze.load_windows("oscar_base")
    for e in m.itertuples():
        v = s.loc[e.event_id].to_numpy(dtype=float)
        wd0 = (dt.date.fromisoformat(e.event_date) - dt.timedelta(days=60)).weekday()
        shards[e.shard][e.event_id] = {"wd0": wd0, "v": [None if np.isnan(x) else int(x) for x in v]}
        if e.event_id in bases:   # Academy Awards: the pre-nomination baseline window
            bv, bwd = bases[e.event_id]
            shards[e.shard][e.event_id]["b"] = {"wd0": bwd, "v": [int(x) for x in bv]}
    out = ROOT / "assets/series"
    out.mkdir(parents=True, exist_ok=True)
    for k, d in shards.items():
        (out / f"{k:02d}.json").write_text(json.dumps(d, separators=(",", ":")))

    c = pd.read_csv(ROOT / "results/avg_curve.csv")
    avg = {"day": c.day.tolist()}
    for t in ("death", "award"):
        for k in ("median", "p25", "p75"):
            avg[f"{t}_{k}"] = [r(x, 4) for x in c[f"{t}_{k}"]]
    wins = pd.read_csv(ROOT / "tables/model_wins.csv").to_dict("records")

    edges = np.geomspace(1 / 8, 64, 28)
    lift = {"edges": [r(x, 4) for x in edges]}
    for t in ("death", "award"):
        x = m[m.event_type == t].lift.dropna().clip(edges[0], edges[-1] * 0.999)
        h, _ = np.histogram(x, bins=edges)
        lift[t] = h.tolist()
        lift[f"{t}_n"] = int(len(x))

    occ = pd.read_csv(ROOT / "tables/by_occupation.csv")
    fam = pd.read_csv(ROOT / "tables/by_event_group.csv")
    groups = []
    for e in fam.itertuples():
        groups.append({"label": e.group, "kind": "event", "n": int(e.n), "hl": r(e.half_life_median, 1),
                       "late": r(e.late_share_median), "lift": r(e.lift_median), "peak": r(e.peak_ratio_median, 1)})
    for e in occ[occ.event_type == "death"].itertuples():
        groups.append({"label": e.occupation_group, "kind": "occupation", "n": int(e.n), "hl": r(e.half_life_median, 1),
                       "late": r(e.late_share_median), "lift": r(e.lift_median), "peak": r(e.peak_ratio_median, 1)})

    data = {"events": idx, "avg": avg, "wins": wins, "lift": lift, "groups": groups}
    (ROOT / "assets/data.json").write_text(json.dumps(data, separators=(",", ":")))
    print(f"data.json: {len(idx)} events; {SHARDS} series shards")


if __name__ == "__main__":
    main()
