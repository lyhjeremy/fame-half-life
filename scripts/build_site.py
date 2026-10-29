"""Fill the landing page, write-up fragment and README templates from site/numbers.json.

The write-up fragment is also copied to the shared overview builder's fragments folder
(_ai-projects-tooling/overview-pages/fragments/fame-half-life.html) when that folder exists;
run the builder on it to regenerate overview/index.html.
"""
import json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
PH = re.compile(r"\{\{(\w+)\}\}")


def fill(text, n, name):
    missing = sorted(set(PH.findall(text)) - set(n))
    if missing:
        raise SystemExit(f"numbers missing in {name}: {missing}")
    return PH.sub(lambda m: str(n[m.group(1)]), text)


def main():
    n = json.loads((ROOT / "site/numbers.json").read_text())
    (ROOT / "index.html").write_text(fill((ROOT / "site/index.template.html").read_text(), n, "index"))
    frag = fill((ROOT / "site/overview.fragment.html").read_text(), n, "fragment")
    tooling = ROOT.parent.parent / "_ai-projects-tooling/overview-pages/fragments"
    if tooling.exists():
        (tooling / "fame-half-life.html").write_text(frag)
    (ROOT / "README.md").write_text(fill((ROOT / "site/README.template.md").read_text(), n, "README"))
    w = ROOT / "site/writeup.template.md"
    if w.exists():
        (ROOT / "writeup.md").write_text(fill(w.read_text(), n, "writeup"))
    print("index.html, README.md, writeup.md and the write-up fragment written")


if __name__ == "__main__":
    main()
