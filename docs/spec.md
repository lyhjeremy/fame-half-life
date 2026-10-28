# Fame Half-Life: spec

Project 40. Drafted 2026-10-28. Status: locked 2026-10-28, approved for build.

## 1. Question

When someone suddenly becomes news, how fast does the world stop looking them up? Using daily English Wikipedia pageviews around deaths and major awards from 2016 to 2025, measure the half-life of a spike in attention, test which curve the fade follows, and check whether attention settles back to where it was or stays higher for good.

Working headline: "Half the extra attention a death brings is gone in __ days; a year later the page still draws __ times its old traffic. Awards fade __ and settle __."

## 2. Prior work to read and cite

- Candia, Jara-Figueroa, Rodriguez-Sickert, Barabási and Hidalgo (2019), "The universal decay of collective memory and attention", Nature Human Behaviour: a two-phase (biexponential) decay of attention to people and works.
- Wikimedia pageview definitions (the `user` agent filter, what counts as a view, known bot leakage).

Citations are confirmed from the source before they appear in copy.

## 3. Locked decisions

| Decision | Choice |
|---|---|
| Running cost | $0. Static site on GitHub Pages. |
| Pageviews | Wikimedia REST API, `per-article/en.wikipedia/all-access/user/daily`. Free, no key; requests carry a User-Agent naming the project and contact page, and stay well under the published rate limit. Data starts July 2015. |
| Events | Wikidata SPARQL query service, with the query text committed so the list is reproducible. |
| Raw cache | Outside My Drive (`$FAME_CACHE`), one JSON per article. |
| Repo | `fame-half-life` |
| Family | language (Newsreader, seal red and ink blue) |
| Language | Python: pandas, scipy (curve fits), statsmodels; plain JS and inline SVG for the page. |
| LLM calls | None. |
| Numbers in copy | Generated only, Fuel Lockstep pattern. |

## 4. The event list, fixed before any pageview is fetched

The list is the subjective part, so the rule is written here and frozen in `data/events.csv` before analysis.

1. **Deaths.** Humans (Wikidata `P31 = Q5`) with an English Wikipedia article and a date of death (`P570`) from 1 January 2016 to 31 October 2025, with at least 30 Wikidata sitelinks (articles in 30 or more language editions) as a fame floor fixed in advance. A probe on 2026-10-28 found 104 such deaths in the first half of 2023, so the full decade should give roughly 2,000.
2. **Awards.** Winners, at the date of announcement, of the Nobel Prizes (all six), the Academy Awards for the four acting categories and Best Director, the Ballon d'Or, and the Booker Prize, 2016 to 2025. Announcement dates come from Wikidata qualifiers where present, otherwise from the award's own list page, recorded per row.
3. **Exclusions.** People whose article was created within 30 days before the event (no baseline exists); and, for awards, people who die within a year of winning, so the two event types do not contaminate each other.
4. Ending at October 2025 leaves every event a full year of aftermath inside the data.

## 5. Measures and analysis

Per event, using days −60 to +365:

| Measure | Definition |
|---|---|
| Baseline | median daily views, days −60 to −8 |
| Peak | maximum daily views, days 0 to +3 (deaths are often reported the day after) |
| Excess | views minus baseline |
| Half-life | first day the 7-day centered mean of excess falls below half the peak excess |
| Lift | median views on days +335 to +365 divided by baseline |

1. **EDA.** Distribution of peaks, baselines and lifts; the share of events with no visible spike; weekly seasonality in pageviews (subtracted by day-of-week factors from the baseline window).
2. **Curve shape.** Fit three models to each event's excess on days +1 to +365: exponential, power law, and the biexponential from Candia et al. Compare with AIC on log excess and report the share of events each model wins, overall and by event type.
3. **What predicts a longer half-life.** Regression of log half-life and log lift on event type, prior fame (log baseline), age at death, occupation group (Wikidata `P106`, mapped to about eight groups), and year.
4. **Checks.**
   - Bot leakage: rerun with a cap on any single day above 50 times the median of its neighbors.
   - Redirects: pageviews follow titles, not people. Each title is resolved through Wikidata at fetch time and the rename history checked for the window; events with a mid-window rename are dropped and counted.
   - Sensitivity of the half-life to the smoothing window (3, 7, 14 days).

## 6. Outputs

- Interactive piece: search any person in the dataset and see their curve with the fitted decay and their half-life; plus a chart of half-life by event type and occupation.
- Static figures: the averaged curve for deaths and for awards on a log scale; model-win shares; lift distribution.
- `README.md`, `writeup.md`, landing page, `/overview/` fragment, `tables/`, `results/numbers.json`.
- lyhjeremy.com card, profile hub row.

## 7. Limitations to state on the page

- English Wikipedia only, and pageviews measure looking something up, not caring about it.
- The sitelink floor shapes who counts as famous and leans toward people known internationally.
- Some automated traffic passes the `user` filter.
- A death or award can coincide with other news about the same person (a film release, a scandal), which inflates the spike; nothing in the data separates the two.

## 8. Phases

| Phase | Deliverable | Done when |
|---|---|---|
| 0 | Repo skeleton, SPARQL queries, `events.csv` frozen with counts per type and year | list frozen and committed before any pageview fetch |
| 1 | Pageview fetch with cache and resume, rename check, per-event measures | every event has a measure row or a logged drop reason |
| 2 | Curve fits, model comparison, regressions, checks | `numbers.json` written, blanks filled |
| 3 | Writeup, overview with the search piece, landing page | designcheck, 390px, live check |
| 4 | Hub card, profile row, PROJECTS_SUMMARY, handoff | live link check clean |

## 9. Decisions (Jeremy, 2026-10-28)

1. Events: deaths and the awards listed in section 4.
2. Live lookup: yes. A box on the page fetches any English Wikipedia article's daily pageviews from the Wikimedia API in the visitor's browser and fits the same curves client-side. No backend. A `/privacy/` page is required and linked from the footer: it says the article title and dates go from the visitor's browser to Wikimedia, nothing goes to any server of this project, and links Wikimedia's privacy policy. The box handles API errors, missing articles and rate limits with plain messages and a skeleton loader while fetching.
3. Fame floor: 30 sitelinks.
4. Name: `fame-half-life`.

## 10. Cut lines

First to go: the occupation regression, then the Booker and Ballon d'Or rows. The project fails if fewer than 500 deaths survive the exclusions; then the floor drops to 20 sitelinks, decided and recorded before any result is looked at.
