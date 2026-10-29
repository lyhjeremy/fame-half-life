"""Write data/academy_nominations.csv: the day each year's Academy Award nominations were
announced, for the pre-season Oscar baseline (post-audit correction, 2026-10-29).

Each date is read from the "Winners and nominees" sentence of that ceremony's English
Wikipedia article, and the first citation on that sentence is recorded with it.
"""
import pathlib, re, sys
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import fetch_events as fe

ROOT = pathlib.Path(__file__).resolve().parent.parent
ORD = {88: "88th", 89: "89th", 90: "90th", 91: "91st", 92: "92nd", 93: "93rd", 94: "94th", 95: "95th", 96: "96th", 97: "97th"}
SENT = re.compile(r"The nominees for the \d+\w\w Academy Awards were announced on ((?:January|February|March) \d{1,2}, \d{4})[^<]*(<ref[^>]*>.*?</ref>|<ref[^>]*/>)?", re.S)


def main():
    rows = []
    for n, o in ORD.items():
        page = f"{o} Academy Awards"
        w = fe.enwiki({"action": "parse", "page": page, "prop": "wikitext", "redirects": 1})["parse"]["wikitext"]
        m = SENT.search(w)
        date = pd.to_datetime(m.group(1)).date()
        ref = m.group(2) or ""
        url = re.search(r"url\s*=\s*([^\s|}]+)", ref)
        pub = re.search(r"(?:website|work|publisher)\s*=\s*([^|}]+)", ref)
        rows.append({"ceremony": n, "nominations_announced": date.isoformat(),
                     "source": f"English Wikipedia, {page}",
                     "cited_url": url.group(1) if url else "", "cited_publisher": pub.group(1).strip().strip("'[]") if pub else ""})
    out = pd.DataFrame(rows)
    out.to_csv(ROOT / "data/academy_nominations.csv", index=False)
    print(out.to_string())


if __name__ == "__main__":
    main()
