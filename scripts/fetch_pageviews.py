"""Fetch daily English Wikipedia pageviews for every kept event in data/events.csv.

For each event:
  1. resolve the article's current title through Wikidata (enwiki sitelink) at fetch time;
  2. read the article's revision history over the window and look for page moves
     (a move leaves a revision whose comment reads "moved page [[A]] to [[B]]");
     pageviews follow titles, so an event with a move inside the window is dropped;
  3. fetch daily views, all-access, agent=user, for days -60 to +365.

Every response is cached under $FAME_CACHE, so a rerun resumes where it stopped.
Writes data/series.csv.gz (one row per event, columns d-60 ... d365) and
data/fetch_log.csv (one row per kept event, with a drop reason where there is one).
"""
import concurrent.futures as cf, datetime as dt, pathlib, re, sys, urllib.parse
import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import wm

ROOT = pathlib.Path(__file__).resolve().parent.parent
PRE, POST = 60, 365
LAST = dt.date(2026, 10, 27)      # last complete day of data on the fetch date, 2026-10-28
PV = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{t}/daily/{a}/{b}"
MOVE = re.compile(r"moved page \[\[", re.I)


def current_titles(qids):
    out = {}
    qids = sorted(set(qids))
    for i in range(0, len(qids), 50):
        url = ("https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&props=sitelinks"
               "&sitefilter=enwiki&ids=" + "|".join(qids[i:i + 50]))
        d = wm.get_json(url, kind="wbtitles")
        for k, e in d.get("entities", {}).items():
            out[k] = e.get("sitelinks", {}).get("enwiki", {}).get("title")
    return out


def moves(title, start, end):
    """Timestamps of page moves recorded in the article's history between start and end."""
    found, cont = [], {}
    while True:
        params = {"action": "query", "prop": "revisions", "titles": title, "rvprop": "timestamp|comment",
                  "rvlimit": "max", "rvdir": "newer", "rvstart": f"{start}T00:00:00Z", "rvend": f"{end}T23:59:59Z",
                  "format": "json", "formatversion": 2, **cont}
        d = wm.get_json("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params), kind="revisions")
        for p in d.get("query", {}).get("pages", []):
            for r in p.get("revisions", []):
                if MOVE.search(r.get("comment", "") or ""):
                    found.append(r["timestamp"][:10])
        if "continue" not in d:
            return found
        cont = {"rvcontinue": d["continue"]["rvcontinue"], "continue": d["continue"]["continue"]}


def views(title, start, end):
    url = PV.format(t=urllib.parse.quote(title.replace(" ", "_"), safe=""), a=start.strftime("%Y%m%d"),
                    b=end.strftime("%Y%m%d"))
    d = wm.get_json(url, kind="pageviews")
    if d.get("_status") == 404:
        return None
    return {it["timestamp"][:8]: it["views"] for it in d.get("items", [])}


def one(r):
    day0 = dt.date.fromisoformat(r.event_date)
    start, end = day0 - dt.timedelta(days=PRE), min(day0 + dt.timedelta(days=POST), LAST)
    title = r.current_title
    log = {"event_id": r.event_id, "current_title": title, "title_changed": title != r.title,
           "moves_in_window": "", "drop_reason": ""}
    if not title:
        log["drop_reason"] = "no English article at fetch time"
        return log, None
    mv = moves(title, start, end)
    log["moves_in_window"] = ";".join(mv)
    if mv:
        log["drop_reason"] = "article renamed inside the window"
        return log, None
    v = views(title, start, end)
    if v is None:
        log["drop_reason"] = "no pageview data"
        return log, None
    row = np.full(PRE + POST + 1, np.nan)
    for k in range(PRE + POST + 1):
        d = day0 + dt.timedelta(days=k - PRE)
        if d <= end:
            row[k] = v.get(d.strftime("%Y%m%d"), 0)   # the API omits days with no views
    return log, row


def main():
    ev = pd.read_csv(ROOT / "data/events.csv", keep_default_na=False)
    ev = ev[ev.excluded_reason == ""].copy()
    cur = current_titles(ev.qid)
    ev["current_title"] = ev.qid.map(cur)
    logs, rows = [], {}
    with cf.ThreadPoolExecutor(3) as ex:
        for i, (log, row) in enumerate(ex.map(one, ev.itertuples())):
            logs.append(log)
            if row is not None:
                rows[log["event_id"]] = row
            if i % 50 == 0:
                print(f"{i}/{len(ev)}", flush=True)
    lg = pd.DataFrame(logs)
    lg.to_csv(ROOT / "data/fetch_log.csv", index=False)
    s = pd.DataFrame.from_dict(rows, orient="index", columns=[f"d{k - PRE}" for k in range(PRE + POST + 1)])
    s.index.name = "event_id"
    s.to_csv(ROOT / "data/series.csv.gz", float_format="%.0f", compression={"method": "gzip", "mtime": 0})
    print(lg.drop_reason.replace("", "kept").value_counts())


if __name__ == "__main__":
    main()
