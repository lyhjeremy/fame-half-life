# Fame Half-Life

How fast does the world stop looking someone up? This project measures the spike in daily English Wikipedia pageviews around {{nDeaths}} deaths and {{nAwards}} major awards from 2016 to October 2025, tests which curve the fade follows, and checks where attention settles a year later. The page also has a live box that fetches any article's views from Wikimedia and fits the same curves in your browser.

[Interactive site](https://lyhjeremy.github.io/fame-half-life/) · [Write-up](https://lyhjeremy.github.io/fame-half-life/overview/) · [Long-form notes](writeup.md) · [Privacy](https://lyhjeremy.github.io/fame-half-life/privacy/)

Design and copy follow [these standards](https://github.com/lyhjeremy/lyhjeremy/blob/main/DESIGN_STANDARDS.md).

## Results

{{readmeResults}}

![Median daily views as a multiple of baseline, days -60 to +365, for deaths and awards on a log scale](figures/average_curve.png)

## Events

| Type | Rule | Candidates | Analyzed |
|---|---|---|---|
| Deaths | humans with an English article, 30+ Wikidata sitelinks, day-precision death date, 1 Jan 2016 to 31 Oct 2025 | {{nDeathCand}} | {{nDeaths}} |
| Awards | Nobel Prizes (all six), Academy Awards (four acting categories and Best Director), Ballon d'Or, Booker Prize | {{nAwardCand}} | {{nAwards}} |

The list was frozen in `data/events.csv` and committed before any pageview was fetched. Exclusions: article created less than 30 days before the event ({{nCreatedDeath}} deaths, {{nCreatedAward}} awards), article renamed inside the window ({{nRenamed}}), baseline under one view a day ({{nNoBase}}). Every data decision is in [`docs/decisions.md`](docs/decisions.md).

## Measures

| Measure | Definition |
|---|---|
| Baseline | median daily views, days -60 to -8; for the Academy Awards, the 53 days ending 8 days before that year's nominations (`data/academy_nominations.csv`) |
| Peak | maximum daily views, days 0 to +3 |
| Half-life | days from the smoothed peak until the centered 7-day mean of excess views falls below half of it |
| Spike | peak at least twice the baseline on days 0 to 3; "delayed" if that only happens on days 4 to 30 |
| After week one | share of the first year's excess views that arrive more than 7 days after the peak |
| Lift | median views on days +335 to +365 divided by baseline |

Views are adjusted for day of week using factors from the baseline window. Three decay models (exponential, power law, and the biexponential form of Candia et al. 2019) are added to the baseline, fitted to log(1 + daily views) on every day after the peak, and compared by AIC. `scripts/simulate_selection.py` checks on simulated series that the comparison recovers the true model (`tables/model_recovery.csv`). The spec's original measures are kept as sensitivity rows (`tables/half_life_sensitivity.csv`, `tables/oscar_baseline.csv`, the `spec_` columns of `tables/model_wins.csv`).

## How to run

```bash
pip install -r requirements.txt
export FAME_CACHE=~/data-cache/fame-half-life   # raw responses, outside the repo
python scripts/fetch_events.py      # Wikidata, Nobel API, Wikipedia -> data/events.csv (frozen 2026-10-28; do not rerun)
python scripts/amend_events.py      # post-audit amendment: the three 2022 economics laureates
python scripts/academy_nominations.py   # data/academy_nominations.csv
python scripts/fetch_pageviews.py   # pageviews and rename check -> data/fetch_log.csv; series files rebuilt from the cache
python scripts/simulate_selection.py    # tables/model_recovery.csv
python scripts/analyze.py           # results/ and tables/
python scripts/make_figures.py      # figures/
python scripts/export_numbers.py    # site/numbers.json
python scripts/export_web.py        # assets/data.json, assets/series/
python scripts/build_site.py        # index.html, README.md, writeup.md, write-up fragment
python scripts/check_fit_parity.py  # browser fits against Python fits (needs node)
```

The daily series are not committed. `fetch_pageviews.py` rebuilds `data/series.csv.gz` and the Oscar baseline windows from the response cache in `$FAME_CACHE`, offline once the cache exists; from an empty cache it takes 2 to 3 hours, at about two requests a second. The same series are published per event in `assets/series/`.

## Repo layout

| Path | Contents |
|---|---|
| `queries/` | SPARQL text for deaths, Academy Awards, Booker winners and occupation groups |
| `scripts/` | fetchers, `fits.py` (measures and models), analysis, figures, site builders |
| `data/` | the frozen event list (plus three amended rows), fetch log, occupation groups and Academy nominations dates |
| `results/`, `tables/` | every number the pages quote |
| `index.html`, `assets/` | the interactive page; `assets/fit.js` is a line-for-line port of `scripts/fits.py` |
| `overview/` | the write-up, generated from `site/overview.fragment.html` by the shared overview builder |
| `privacy/` | what the live lookup sends to Wikimedia |

Stack: Python (pandas, NumPy, statsmodels, matplotlib) and plain HTML, CSS and JavaScript with no libraries. Hosted on GitHub Pages; no server.

## Sources

- Pageviews: [Wikimedia REST API](https://wikimedia.org/api/rest_v1/), `per-article/en.wikipedia/all-access/user/daily`.
- Events: [Wikidata Query Service](https://query.wikidata.org/), the [Nobel Prize API](https://www.nobelprize.org/about/developer-zone-2/), and English Wikipedia articles on each year's Ballon d'Or and Booker Prize.
- Candia, C., Jara-Figueroa, C., Rodriguez-Sickert, C., Barabási, A.-L. and Hidalgo, C. A. (2019). The universal decay of collective memory and attention. *Nature Human Behaviour* 3, 82–91. [doi:10.1038/s41562-018-0474-5](https://doi.org/10.1038/s41562-018-0474-5)

## License

Code under the MIT License. Pageview data from the Wikimedia Foundation (CC0); Wikidata content is CC0.
