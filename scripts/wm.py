"""Polite HTTP access to Wikimedia services, with an on-disk cache.

Every response is cached as one JSON file under $FAME_CACHE (default
~/data-cache/fame-half-life), outside the repo and outside Google Drive.
Requests carry a User-Agent naming the project and a contact page, and back off
on 429 and 5xx answers.
"""
import hashlib, json, os, pathlib, threading, time, urllib.error, urllib.parse, urllib.request

UA = "fame-half-life/1.0 (https://github.com/lyhjeremy/fame-half-life; https://lyhjeremy.com)"
MIN_GAP = 0.5                 # seconds between live requests to one host, across all threads
_lock = threading.Lock()
_last = {}
CACHE = pathlib.Path(os.environ.get("FAME_CACHE", pathlib.Path.home() / "data-cache/fame-half-life"))
SPARQL = "https://query.wikidata.org/sparql"


def _path(kind, key):
    h = hashlib.sha1(key.encode()).hexdigest()
    p = CACHE / kind / h[:2] / f"{h}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def get_json(url, kind="misc", data=None, tries=10, timeout=90):
    """GET (or POST when data is given) a JSON URL, cached. A 404 is cached as {"_status": 404}."""
    key = url + ("|" + data if data else "")
    p = _path(kind, key)
    if p.exists():
        return json.loads(p.read_text())
    wait = 5.0
    for attempt in range(tries):
        host = urllib.parse.urlsplit(url).netloc
        while True:
            with _lock:
                gap = MIN_GAP - (time.time() - _last.get(host, 0.0))
                if gap <= 0:
                    _last[host] = time.time()
                    break
            time.sleep(gap)
        req = urllib.request.Request(url, data=data.encode() if data else None,
                                     headers={"User-Agent": UA, "Accept": "application/json",
                                              **({"Content-Type": "application/x-www-form-urlencoded"} if data else {})})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                out = json.loads(r.read().decode())
            p.write_text(json.dumps(out))
            return out
        except urllib.error.HTTPError as e:
            if e.code == 404:
                out = {"_status": 404}
                p.write_text(json.dumps(out))
                return out
            if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                ra = e.headers.get("Retry-After")
                with open(CACHE / "throttle.log", "a") as lf:
                    lf.write(f"{time.strftime('%H:%M:%S')} {e.code} {urllib.parse.urlsplit(url).netloc} retry-after={ra} wait={wait}\n")
                time.sleep(float(ra) if ra and ra.isdigit() else wait)
                wait *= 2
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            # network faults (DNS failure, reset connection) are retried, never cached as missing data
            if attempt < tries - 1:
                time.sleep(wait)
                wait *= 2
                continue
            raise


def sparql(query, kind="sparql"):
    data = urllib.parse.urlencode({"query": query, "format": "json"})
    out = get_json(SPARQL, kind=kind, data=data, timeout=120)
    return out["results"]["bindings"]


def val(row, k):
    v = row.get(k)
    return v["value"] if v else None
