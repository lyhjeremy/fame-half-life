"""Fetch daily English Wikipedia pageviews for every kept event in data/events.csv.

For each event:
  1. resolve the article's current title through Wikidata (enwiki sitelink) at fetch time;
  2. read the article's revision history from day -60 to the fetch date and look for page
     moves (a move leaves a revision whose comment reads "moved page [[A]] to [[B]]");
     pageviews follow titles, so an event with a move inside the window is dropped, and
     for one moved later the views are read under the title it had during the window;
  3. fetch daily views, all-access, agent=user, for days -60 to +365.

Every response is cached under $FAME_CACHE, so a rerun resumes where it stopped.
Academy Award events also get their pre-season window: the 53 days ending 8 days before
that year's nominations were announced (data/academy_nominations.csv), read under the same
title (post-audit correction, 2026-10-29).

Writes data/fetch_log.csv (committed; one row per kept event, with a drop reason where
there is one), and data/series.csv.gz (one row per event, columns d-60 ... d365) and
data/oscar_base.csv.gz (pre-season windows), which are rebuilt from the cache and not
committed.
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
MOVE = re.compile(r"moved page \[\[([^\]]+)\]\] to \[\[([^\]]+)\]\]", re.I)
FETCHED = dt.date(2026, 10, 28)


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
    """(date, old title, new title) for page moves recorded in the article's history between start and end."""
    found, cont = [], {}
    while True:
        params = {"action": "query", "prop": "revisions", "titles": title, "rvprop": "timestamp|comment",
                  "rvlimit": "max", "rvdir": "newer", "rvstart": f"{start}T00:00:00Z", "rvend": f"{end}T23:59:59Z",
                  "format": "json", "formatversion": 2, **cont}
        d = wm.get_json("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params), kind="revisions")
        for p in d.get("query", {}).get("pages", []):
            for r in p.get("revisions", []):
                mm = MOVE.search(r.get("comment", "") or "")
                if mm:
                    found.append((r["timestamp"][:10], mm.group(1), mm.group(2)))
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


NOMS = None


def nominations():
    global NOMS
    if NOMS is None:
        n = pd.read_csv(ROOT / "data/academy_nominations.csv")
        NOMS = {d[:4]: dt.date.fromisoformat(d) for d in n.nominations_announced}
    return NOMS


def base_window(title, event_date):
    """Views over days -60 to -8 relative to the nominations announcement."""
    nom = nominations()[event_date[:4]]
    a, b = nom - dt.timedelta(days=60), nom - dt.timedelta(days=8)
    v = views(title, a, b)
    if v is None:
        return None
    return nom.isoformat(), a.isoformat(), [v.get((a + dt.timedelta(days=k)).strftime("%Y%m%d"), 0)
                                            for k in range((b - a).days + 1)]


def one(r):
    day0 = dt.date.fromisoformat(r.event_date)
    start, end = day0 - dt.timedelta(days=PRE), min(day0 + dt.timedelta(days=POST), LAST)
    title = r.current_title
    log = {"event_id": r.event_id, "current_title": title, "title_changed": title != r.title,
           "moves_in_window": "", "moves_after_window": "", "title_used": "", "drop_reason": ""}
    if not title:
        log["drop_reason"] = "no English article at fetch time"
        return log, None
    mv = moves(title, start, end)
    log["moves_in_window"] = ";".join(d for d, _, _ in mv)
    if mv:
        log["drop_reason"] = "article renamed inside the window"
        return log, None
    # A move after the window means the article had another title during it, and its
    # views were counted under that title. Every title in the later move history is a
    # candidate; the one with the most views in the window is the article (the others
    # were redirects or did not exist yet).
    later = moves(title, end + dt.timedelta(days=1), FETCHED)
    log["title_used"] = title
    v = None
    if later:
        log["moves_after_window"] = ";".join(d for d, _, _ in later)
        cands = list(dict.fromkeys([t for _, a, b in later for t in (a, b)] + [title]))
        best = -1
        for c in cands:
            cv = views(c, start, end)
            tot = sum(cv.values()) if cv else -1
            if tot > best:
                best, v, log["title_used"] = tot, cv, c
    else:
        v = views(title, start, end)
    if v is None:
        log["drop_reason"] = "no pageview data"
        return log, None
    row = np.full(PRE + POST + 1, np.nan)
    for k in range(PRE + POST + 1):
        d = day0 + dt.timedelta(days=k - PRE)
        if d <= end:
            row[k] = v.get(d.strftime("%Y%m%d"), 0)   # the API omits days with no views
    if r.award.startswith("Academy Award"):
        bw = base_window(log["title_used"], r.event_date)
        if bw:
            log["base"] = bw
        # Sensitivity only: days -150 to -90 before the ceremony, the auditor's alternative.
        e0 = dt.date.fromisoformat(r.event_date)
        ea, eb = e0 - dt.timedelta(days=150), e0 - dt.timedelta(days=90)
        ev_ = views(log["title_used"], ea, eb)
        if ev_ is not None:
            log["early"] = (ea.isoformat(), [ev_.get((ea + dt.timedelta(days=k)).strftime("%Y%m%d"), 0)
                                             for k in range((eb - ea).days + 1)])
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
    base = {l["event_id"]: l.pop("base") for l in logs if "base" in l}
    early = {l["event_id"]: l.pop("early") for l in logs if "early" in l}
    lg = pd.DataFrame(logs)
    lg.to_csv(ROOT / "data/fetch_log.csv", index=False)
    s = pd.DataFrame.from_dict(rows, orient="index", columns=[f"d{k - PRE}" for k in range(PRE + POST + 1)])
    s.index.name = "event_id"
    s.to_csv(ROOT / "data/series.csv.gz", float_format="%.0f", compression={"method": "gzip", "mtime": 0})
    b = pd.DataFrame([{"event_id": k, "nominations": n, "start": st, **{f"b{j}": x for j, x in enumerate(v)}}
                      for k, (n, st, v) in base.items()])
    b.to_csv(ROOT / "data/oscar_base.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    e = pd.DataFrame([{"event_id": k, "start": st, **{f"b{j}": x for j, x in enumerate(v)}} for k, (st, v) in early.items()])
    e.to_csv(ROOT / "data/oscar_early.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    print(lg.drop_reason.replace("", "kept").value_counts())


if __name__ == "__main__":
    main()
