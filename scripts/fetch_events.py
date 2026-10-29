"""Build and freeze the event list, data/events.csv, before any pageview is fetched.

Rules (docs/spec.md, section 4):
  deaths  humans with an English Wikipedia article, 30+ Wikidata sitelinks, and a
          day-precision date of death from 2016-01-01 to 2025-10-31
  awards  Nobel Prizes (all six), Academy Awards (four acting categories and Best
          Director), Ballon d'Or, Booker Prize, announced 2016-01-01 to 2025-10-31
  exclude articles created later than 30 days before the event (no baseline);
          award winners who died within a year of winning

Sources for each award's announcement date are recorded per row in `date_source`.
Writes data/events.csv, data/occupation_groups.csv and data/events_counts.csv.
"""
import collections, concurrent.futures as cf, datetime as dt, json, pathlib, re, sys, urllib.parse
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import wm

ROOT = pathlib.Path(__file__).resolve().parent.parent
Q = ROOT / "queries"
START, END = dt.date(2016, 1, 1), dt.date(2025, 10, 31)
WD = "http://www.wikidata.org/entity/"

# Occupation groups, in priority order: a person takes the group of the first
# occupation listed on their Wikidata item that maps to any group; an occupation
# that maps to several groups takes the earliest group in this list.
GROUPS = [
    ("sport", ["Q2066131", "Q50995749", "Q41583"]),                    # athlete, sportsperson, coach
    ("politics and law", ["Q82955", "Q193391", "Q116", "Q189290", "Q16533", "Q40348", "Q372436"]),  # politician, diplomat, monarch, military officer, judge, lawyer, statesperson
    ("screen", ["Q33999", "Q2526255", "Q947873", "Q245068", "Q3282637", "Q28389"]),  # actor, film director, TV presenter, comedian, film producer, screenwriter
    ("music", ["Q639669", "Q177220", "Q36834", "Q753110", "Q130857"]),  # musician, singer, composer, songwriter, DJ
    ("writing and journalism", ["Q36180", "Q1930187", "Q49757"]),       # writer, journalist, poet
    ("science and academia", ["Q901", "Q3400985", "Q1622272", "Q39631", "Q81096", "Q4964182", "Q188094"]),  # scientist, academic, university teacher, physician, engineer, philosopher, economist
    ("business", ["Q43845", "Q131524"]),                                # businessperson, entrepreneur
    ("visual arts and design", ["Q3391743", "Q42973", "Q3501317", "Q33231", "Q1028181"]),  # visual artist, architect, fashion designer, photographer, painter
    ("religion", ["Q250867", "Q1234713"]),                              # cleric, theologian
]
ROOT_TO_GROUP = {}
for g, roots in GROUPS:
    for r in roots:
        ROOT_TO_GROUP.setdefault(r, g)
GROUP_ORDER = [g for g, _ in GROUPS]

NOBEL = {"phy": "Nobel Prize in Physics", "che": "Nobel Prize in Chemistry", "med": "Nobel Prize in Physiology or Medicine",
         "lit": "Nobel Prize in Literature", "pea": "Nobel Peace Prize", "eco": "Nobel Memorial Prize in Economic Sciences"}
OSCAR = {"Q103916": "Academy Award for Best Actor", "Q103618": "Academy Award for Best Actress",
         "Q106291": "Academy Award for Best Supporting Actor", "Q106301": "Academy Award for Best Supporting Actress",
         "Q103360": "Academy Award for Best Director"}
# The Nobel Prize API's dateAwarded is checked against the prize year. The 2018 Literature
# prize was announced on 10 October 2019, together with 2019's, so its mismatch is real.
# The API gives 2011-10-10 for the 2022 Economic Sciences prize; the prize was announced
# on 10 October 2022 (the nobelprize.org press release of that date, cited in the English
# Wikipedia articles on Bernanke, Diamond and Dybvig).
NOBEL_LATE_OK = {(2018, "lit")}
NOBEL_DATE_FIX = {(2022, "eco"): "2022-10-10"}
MONTHS = "January February March April May June July August September October November December".split()


def qid(uri):
    return uri.rsplit("/", 1)[-1]


def half_years():
    y, m = 2016, 1
    while True:
        s = dt.date(y, m, 1)
        e = dt.date(y + (m == 7), 1 if m == 7 else 7, 1)
        if s > END:
            return
        yield s, min(e, END + dt.timedelta(days=1))
        y, m = (y + 1, 1) if m == 7 else (y, 7)


def deaths():
    tmpl = (Q / "deaths.rq").read_text()
    rows = []
    for s, e in half_years():
        q = tmpl.replace("{start}", s.isoformat()).replace("{end}", e.isoformat())
        r = wm.sparql(q)
        print(f"deaths {s} to {e}: {len(r)} rows", flush=True)
        for x in r:
            rows.append({"qid": qid(wm.val(x, "person")), "dod": wm.val(x, "dod")[:10],
                         "prec": int(wm.val(x, "prec")), "sitelinks": int(wm.val(x, "sl"))})
    d = pd.DataFrame(rows)
    out, dropped = [], collections.Counter()
    for q_, g in d.groupby("qid"):
        days = sorted(set(g.loc[g.prec >= 11, "dod"]))
        if not days:
            dropped["death date not given to the day"] += 1
            continue
        if len(days) > 1:
            dropped["conflicting death dates"] += 1
            continue
        out.append({"qid": q_, "event_type": "death", "award": "", "event_date": days[0],
                    "date_source": "Wikidata P570"})
    return out, dropped


def nobel():
    out = []
    for y in range(START.year, END.year + 1):
        for cat in NOBEL:
            url = f"https://api.nobelprize.org/2.1/nobelPrizes?nobelPrizeYear={y}&nobelPrizeCategory={cat}"
            d = wm.get_json(url, kind="nobel")
            for p in d.get("nobelPrizes", []):
                date = p.get("dateAwarded")
                if (y, cat) in NOBEL_DATE_FIX:
                    date = NOBEL_DATE_FIX[(y, cat)]
                elif date and int(date[:4]) != y and (y, cat) not in NOBEL_LATE_OK:
                    raise SystemExit(f"nobel {y} {cat}: dateAwarded {date} is outside the prize year; add it to NOBEL_DATE_FIX")
                for lau in p.get("laureates", []):
                    if "knownName" not in lau:      # organizations carry orgName instead
                        continue
                    det = wm.get_json(lau["links"][0]["href"].replace("/2/", "/2.1/"), kind="nobel")
                    det = det[0] if isinstance(det, list) else det
                    wd_ = (det.get("wikidata") or {}).get("id")
                    if not wd_ or not date:
                        print("nobel: no wikidata id or date for", lau["knownName"]["en"], y, cat)
                        continue
                    out.append({"qid": wd_, "event_type": "award", "award": NOBEL[cat], "event_date": date,
                                "date_source": "Nobel Prize API dateAwarded" if (y, cat) not in NOBEL_DATE_FIX else "nobelprize.org press release, 10 October 2022"})
    return out


def oscars():
    out = []
    for x in wm.sparql((Q / "oscars.rq").read_text()):
        out.append({"qid": qid(wm.val(x, "person")), "event_type": "award", "award": OSCAR[qid(wm.val(x, "award"))],
                    "event_date": wm.val(x, "cerDate")[:10],
                    "date_source": f"Wikidata P585 of ceremony {qid(wm.val(x, 'cer'))}"})
    return out


def enwiki(params):
    return wm.get_json("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        {**params, "format": "json", "formatversion": 2}), kind="mediawiki")


def parse_date(s):
    m = re.search(r"(\d{1,2}) (" + "|".join(MONTHS) + r") (\d{4})", s)
    if m:
        return dt.date(int(m.group(3)), MONTHS.index(m.group(2)) + 1, int(m.group(1)))
    m = re.search(r"start date\|(\d{4})\|(\d{1,2})\|(\d{1,2})", s)
    if m:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def title_to_qid(titles):
    d = enwiki({"action": "query", "prop": "pageprops", "ppprop": "wikibase_item", "redirects": 1,
                "titles": "|".join(titles)})
    norm = {}
    for k in ("normalized", "redirects"):
        for r in d["query"].get(k, []):
            norm[r["from"]] = r["to"]
    by = {p["title"]: p.get("pageprops", {}).get("wikibase_item") for p in d["query"]["pages"]}
    res = {}
    for t in titles:
        u = t
        while u in norm:
            u = norm[u]
        res[t] = by.get(u)
    return res


def ballon():
    out = []
    for y in range(START.year, END.year + 1):
        page = f"{y} Ballon d'Or"
        d = enwiki({"action": "parse", "page": page, "prop": "wikitext", "redirects": 1})
        if "error" in d:
            print(f"ballon: no page for {y} (2020 was cancelled)")
            continue
        w = d["parse"]["wikitext"]
        dm = re.search(r"^\s*\|\s*date\s*=([^\n]*)", w, re.M)
        wm_ = re.search(r"^\s*\|\s*award1_winner\s*=[^\n]*?\[\[([^\]|]+)", w, re.M)
        date = parse_date(dm.group(1)) if dm else None
        if not date or not wm_:
            print(f"ballon: no ceremony date or winner on {page} (2020 was cancelled)")
            continue
        win = wm_.group(1)
        q_ = title_to_qid([win])[win]
        out.append({"qid": q_, "event_type": "award", "award": "Ballon d'Or", "event_date": date.isoformat(),
                    "date_source": f"English Wikipedia, {page} (infobox date)"})
    return out


def booker():
    years = collections.defaultdict(list)
    for x in wm.sparql((Q / "booker.rq").read_text()):
        years[int(wm.val(x, "t")[:4])].append(qid(wm.val(x, "person")))
    out = []
    for y in range(START.year, END.year + 1):
        for page in (f"{y} Booker Prize", f"{y} Man Booker Prize"):   # the prize was the Man Booker until 2019
            d = enwiki({"action": "query", "prop": "extracts", "explaintext": 1, "titles": page, "redirects": 1})
            p = d["query"]["pages"][0]
            if not p.get("missing"):
                break
        text = p.get("extract") or ""
        date = None
        for sent in re.split(r"(?<=\.)\s", text):
            if re.search(r"longlist|shortlist", sent, re.I):
                continue
            if re.search(r"(awarded at a ceremony on|announced on)", sent):
                date = parse_date(sent)
                if date and date.year == y:
                    break
                date = None
        if not date or date > END:
            print(f"booker {y}: no announcement date inside the window ({date})")
            continue
        for q_ in sorted(set(years.get(y, []))):
            out.append({"qid": q_, "event_type": "award", "award": "Booker Prize", "event_date": date.isoformat(),
                        "date_source": f"English Wikipedia, {p['title']} (announcement sentence)"})
    return out


def entities(qids):
    """Ordered occupations, birth and death dates, sitelinks and current enwiki title, from wbgetentities."""
    info = {}
    qids = sorted(set(qids))
    for i in range(0, len(qids), 50):
        chunk = qids[i:i + 50]
        url = ("https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&props=claims|sitelinks"
               "&ids=" + "|".join(chunk))
        d = wm.get_json(url, kind="wbentities")
        for k, e in d.get("entities", {}).items():
            c = e.get("claims", {})

            def times(p):
                vals = []
                for s in c.get(p, []):
                    if s.get("rank") == "deprecated":
                        continue
                    v = s["mainsnak"].get("datavalue", {}).get("value", {})
                    if v.get("time"):
                        vals.append((v["time"][1:11], v.get("precision", 0)))
                return vals
            occ = [s["mainsnak"]["datavalue"]["value"]["id"] for s in c.get("P106", [])
                   if s.get("rank") != "deprecated" and s["mainsnak"].get("datavalue")]
            info[k] = {"occupations": occ, "dob": times("P569"), "dod": times("P570"),
                       "sitelinks": len(e.get("sitelinks", {})),
                       "title": e.get("sitelinks", {}).get("enwiki", {}).get("title")}
        print(f"entities {min(i + 50, len(qids))}/{len(qids)}", end="\r", flush=True)
    print()
    return info


def occupation_groups(occs):
    tmpl = (Q / "occupation_groups.rq").read_text()
    roots = " ".join(f"wd:{r}" for r in ROOT_TO_GROUP)
    hits = collections.defaultdict(set)
    occs = sorted(occs)
    for i in range(0, len(occs), 150):
        vals = " ".join(f"wd:{o}" for o in occs[i:i + 150])
        for x in wm.sparql(tmpl.replace("{values}", vals).replace("{roots}", roots)):
            hits[qid(wm.val(x, "occ"))].add(ROOT_TO_GROUP[qid(wm.val(x, "root"))])
    return {o: min(hits[o], key=GROUP_ORDER.index) for o in hits}


def created(title):
    d = enwiki({"action": "query", "prop": "revisions", "rvprop": "timestamp", "rvlimit": 1, "rvdir": "newer",
                "titles": title})
    p = d["query"]["pages"][0]
    if p.get("missing"):
        return None
    return p["revisions"][0]["timestamp"][:10]


def main():
    d, dropped = deaths()
    a = nobel() + oscars() + ballon() + booker()
    ev = pd.DataFrame(d + a)
    ev = ev[(ev.event_date >= START.isoformat()) & (ev.event_date <= END.isoformat())]
    ev = ev.drop_duplicates(["qid", "event_type", "award", "event_date"])
    # An Academy Award listed twice under one ceremony collapses to one row; two awards
    # to one person on one day (none expected) would stay as two rows.
    info = entities(ev.qid)
    occ_map = occupation_groups({o for v in info.values() for o in v["occupations"]})
    pd.DataFrame(sorted(occ_map.items()), columns=["occupation", "group"]).to_csv(ROOT / "data/occupation_groups.csv", index=False)

    def group(q_):
        for o in info.get(q_, {}).get("occupations", []):
            if o in occ_map:
                return occ_map[o]
        return "other"

    def first_day(vals):
        days = sorted(v for v, p in vals if p >= 11)
        return days[0] if days else (sorted(v for v, p in vals)[0] if vals else None)

    ev["title"] = ev.qid.map(lambda q_: info.get(q_, {}).get("title"))
    ev["sitelinks"] = ev.qid.map(lambda q_: info.get(q_, {}).get("sitelinks"))
    ev["occupation_group"] = ev.qid.map(group)
    ev["birth_date"] = ev.qid.map(lambda q_: first_day(info.get(q_, {}).get("dob", [])))
    ev["death_date"] = ev.qid.map(lambda q_: first_day(info.get(q_, {}).get("dod", [])))
    ev = ev[ev.title.notna()].copy()

    titles = sorted(set(ev.title))
    with cf.ThreadPoolExecutor(3) as ex:
        cr = dict(zip(titles, ex.map(created, titles)))
    ev["article_created"] = ev.title.map(cr)

    def age(r):
        b = r.birth_date
        if not b or b[5:] == "00-00" or b[:1] == "-":
            return None
        try:
            b = dt.date.fromisoformat(b[:4] + ("-07-01" if b[5:7] == "00" else b[4:8] + ("15" if b[8:] == "00" else b[8:])))
        except ValueError:
            return None
        return round((dt.date.fromisoformat(r.event_date) - b).days / 365.25, 1)
    ev["age_at_event"] = ev.apply(age, axis=1)

    def reason(r):
        if not r.article_created:
            return "no English article found"
        if r.event_type == "death" and len({v for v, pr in info[r.qid]["dod"] if pr >= 11}) > 1:
            return "conflicting death dates"
        if dt.date.fromisoformat(r.article_created) > dt.date.fromisoformat(r.event_date) - dt.timedelta(days=30):
            return "article created less than 30 days before the event"
        if r.event_type == "award" and r.death_date:
            dd = dt.date.fromisoformat(r.death_date) if r.death_date[5:] != "00-00" else None
            if dd and dt.date.fromisoformat(r.event_date) <= dd <= dt.date.fromisoformat(r.event_date) + dt.timedelta(days=365):
                return "died within a year of the award"
        return ""
    ev["excluded_reason"] = ev.apply(reason, axis=1)
    ev = ev.sort_values(["event_date", "event_type", "title"]).reset_index(drop=True)
    ev.insert(0, "event_id", [f"{r.event_type[0]}{i:04d}" for i, r in ev.iterrows()])
    cols = ["event_id", "qid", "title", "event_type", "award", "event_date", "date_source", "sitelinks",
            "occupation_group", "birth_date", "death_date", "age_at_event", "article_created", "excluded_reason"]
    ev[cols].to_csv(ROOT / "data/events.csv", index=False)

    ev["year"] = ev.event_date.str[:4]
    kept = ev[ev.excluded_reason == ""]
    counts = pd.concat([ev.groupby(["event_type", "year"]).size().rename("candidates"),
                        kept.groupby(["event_type", "year"]).size().rename("kept")], axis=1).fillna(0).astype(int)
    counts.to_csv(ROOT / "data/events_counts.csv")
    print(counts)
    print("excluded:", ev.excluded_reason.value_counts().to_dict())
    print("deaths dropped before the list for date problems:", dict(dropped))
    (ROOT / "data/events_dropped_dates.json").write_text(json.dumps(dict(dropped), indent=1) + "\n")


if __name__ == "__main__":
    main()
