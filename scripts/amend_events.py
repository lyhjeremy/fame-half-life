"""Post-audit amendment to the frozen event list (2026-10-29).

The Nobel Prize API gives dateAwarded 2011-10-10 for the 2022 Economic Sciences prize, so
the freeze dropped Bernanke, Diamond and Dybvig as outside the window. That is a data bug,
not a rule change: fetch_events.py now checks dateAwarded against the prize year and uses
10 October 2022 for this prize. This script appends the award rows the corrected rule
adds, with new event ids, and leaves every frozen row untouched (rerunning fetch_events.py
would refetch Wikidata as it is today and could change frozen rows).
"""
import datetime as dt, pathlib, sys
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import fetch_events as fe

ROOT = pathlib.Path(__file__).resolve().parent.parent


def write_counts(ev):
    ev = ev.assign(year=ev.event_date.str[:4])
    kept = ev[ev.excluded_reason == ""]
    counts = pd.concat([ev.groupby(["event_type", "year"]).size().rename("candidates"),
                        kept.groupby(["event_type", "year"]).size().rename("kept")], axis=1).fillna(0).astype(int)
    counts.to_csv(ROOT / "data/events_counts.csv")


def main():
    ev = pd.read_csv(ROOT / "data/events.csv", keep_default_na=False)
    have = set(zip(ev.qid, ev.award, ev.event_date))
    new = [r for r in fe.nobel() if (r["qid"], r["award"], r["event_date"]) not in have
           and fe.START.isoformat() <= r["event_date"] <= fe.END.isoformat()]
    if not new:
        print("nothing to amend")
        return
    info = fe.entities([r["qid"] for r in new])
    occ = dict(pd.read_csv(ROOT / "data/occupation_groups.csv").values)
    missing = {o for r in new for o in info[r["qid"]]["occupations"]} - set(occ)
    if missing:
        occ.update(fe.occupation_groups(missing))
    nxt = max(int(i[1:]) for i in ev.event_id) + 1
    rows = []
    for k, r in enumerate(new):
        i = info[r["qid"]]
        dob = sorted(v for v, p in i["dob"] if p >= 11)
        dod = sorted(v for v, p in i["dod"] if p >= 11)
        title = i["title"]
        created = fe.created(title)
        age = None
        if dob:
            age = round((dt.date.fromisoformat(r["event_date"]) - dt.date.fromisoformat(dob[0])).days / 365.25, 1)
        reason = ""
        if dt.date.fromisoformat(created) > dt.date.fromisoformat(r["event_date"]) - dt.timedelta(days=30):
            reason = "article created less than 30 days before the event"
        elif dod and dt.date.fromisoformat(r["event_date"]) <= dt.date.fromisoformat(dod[0]) <= dt.date.fromisoformat(r["event_date"]) + dt.timedelta(days=365):
            reason = "died within a year of the award"
        group = next((occ[o] for o in i["occupations"] if o in occ), "other")
        rows.append({"event_id": f"a{nxt + k:04d}", "qid": r["qid"], "title": title, "event_type": "award",
                     "award": r["award"], "event_date": r["event_date"],
                     "date_source": r["date_source"] + " (corrected 2026-10-29: the API gives 2011-10-10)",
                     "sitelinks": i["sitelinks"], "occupation_group": group,
                     "birth_date": dob[0] if dob else "", "death_date": dod[0] if dod else "",
                     "age_at_event": age if age is not None else "", "article_created": created,
                     "excluded_reason": reason})
    out = pd.concat([ev, pd.DataFrame(rows)], ignore_index=True)
    out.to_csv(ROOT / "data/events.csv", index=False)
    write_counts(out)
    print(pd.DataFrame(rows)[["event_id", "title", "event_date", "excluded_reason"]].to_string())


if __name__ == "__main__":
    main()
