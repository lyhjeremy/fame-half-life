# Fame Half-Life: long-form notes

These notes go with the [interactive page](https://lyhjeremy.github.io/fame-half-life/) and the [write-up](https://lyhjeremy.github.io/fame-half-life/overview/). Every number below is filled in from `results/summary.json` by `scripts/build_site.py`.

## Question

When someone suddenly becomes news, how fast does the world stop looking them up? The data are daily English Wikipedia pageviews around deaths and major awards from 2016 to October 2025. Three things are measured: how fast the spike halves, which curve the fade follows, and whether attention settles back where it was.

## The event list

The rules were written in the spec and the list was committed to `data/events.csv` before any pageview was fetched.

- Deaths: humans with an English article, at least 30 Wikidata sitelinks and a day-precision date of death from 1 January 2016 to 31 October 2025. 1,995 candidates; 39 more were left out before that because their death date was not given to the day or conflicted.
- Awards: the six Nobel Prizes, the Academy Awards for the four acting categories and Best Director, the Ballon d'Or and the Booker Prize. 188 candidates.
- Excluded: article created less than 30 days before the event (21 deaths, 5 awards); award winners who died within a year (0).

At fetch time, 65 events were dropped because the article was moved to a new title inside the window, and 12 had a baseline under one view a day. That leaves 1,905 deaths and 175 awards (107 Nobel, 50 Academy Award, 9 Ballon d'Or, 9 Booker).

## Measures

Views are first divided by day-of-week factors from the baseline window (the median event's busiest weekday runs 1.43 times its quietest). Then, per event:

- baseline: median views, days -60 to -8 (median 202 a day for deaths, 74 for awards);
- peak: maximum of days 0 to +3;
- half-life: days from the peak until the centered 7-day mean of excess views falls below half the peak excess;
- after week one: share of the first year's excess views that arrive more than 7 days after the peak;
- lift: median of days +335 to +365 divided by baseline.

A spike counts as visible when the peak is at least twice the baseline. 3.5% of deaths and 1% of awards have none.

## Results

### The fade

On the median death the page draws 200 times its usual traffic on the peak day, which is the day after the death in 43% of cases. The averaged curve loses half its excess in 1 day and nine tenths in 5 days, and sits at 1.96 times baseline a month later and 1.09 times in the last month of the year. Awards peak at 817 times and lose nine tenths in 4 days. Deaths jump again on day +365, the anniversary; awards climb in the last week of the year as the next year's prize comes round. Measured as specified, the half-life is 1 day for deaths and 1 for awards; it is one day in 95% of deaths with a spike. Most of the attention comes at once: only 29% of a death's first-year excess views (median) arrive after the first week.

### The curve

Three curves were fitted to each event's excess views after the peak: an exponential, a power law, and the biexponential (a sum of two exponentials) that Candia et al. (2019) found in the decay of attention to songs, films and biographies over years. The biexponential has the lowest AIC for 91% of 1,808 deaths and 78% of 139 awards, with a median margin of 25 AIC points over the power law. Its fast part has a median time constant of 5.4 days; the slow part's is 1,418 days, so long that within a year it is close to a flat step above the old baseline. The power law still beats the exponential in 98% of events, which is what a long tail looks like. The two shapes agree with Candia et al. on form; their time scale is years since publication, this one is days since an event.

### The aftermath

A year after a death the median page draws 1.08 times its old traffic, and 59% of pages sit above their baseline. Awards spread far wider. Nobel laureates, with a median of 20 views a day beforehand, keep 8.78 times that. Academy Award winners start from 15,120 a day, already raised by awards season, and end the year at 0.38 times it. Among deaths, each extra year of age at death goes with 2.0% less lift (p < 0.001), and pages that were busier beforehand gain less.

A regression of log lift on event type, log baseline, occupation group and year (OLS, HC3 errors, n = 2,080, R² = 0.25) puts awards 163% above deaths at the same prior traffic (p < 0.001). Among deaths, with age added (n = 1,902, R² = 0.33), each extra year of age at death goes with 2.0% less lift (p < 0.001). The same regression for log half-life explains almost nothing (R² = 0.03), because the half-life barely varies.

### Who lasts

Among deaths, the share of the first year's extra views that arrive after the first week runs from 23% (business) to 33% (writing and journalism), and median lift from 0.97 times (business) to 1.22 times (music). The gap between Nobel and Oscar winners is wider than any gap between occupations.

## Checks

Bot leakage: capping any day above 50 times the median of its six neighbors touches 31 events and changes 1 half-life; median lift with the cap is 1.08 for deaths and 4.16 for awards. Renames: 65 events were dropped because the article moved to a new title inside the window. Smoothing: the median half-life is 2 days with a 3-day window, 1 with 7 and 1 with 14. The spike is narrower than the window, so the specified half-life is one day for most events; the late-share measure and the fitted curves are less sensitive to that choice. Day of week: the median page's busiest weekday draws 1.43 times its quietest, which is why every series is adjusted before measuring.

## Limits

- English Wikipedia only; a view is a lookup, not a measure of how much anyone cares.
- The 30-sitelink floor is today's count and favors people known in many countries.
- Some automated traffic passes the `user` filter.
- Other news about the same person at the same time inflates the spike, and the data cannot separate it.
- Oscar baselines fall in awards season, after the nominations.
- The award sample is small, so differences between prizes are descriptive.
- The half-life as specified saturates at one day for most events; see Checks.

## Reference

Candia, C., Jara-Figueroa, C., Rodriguez-Sickert, C., Barabási, A.-L. and Hidalgo, C. A. (2019). The universal decay of collective memory and attention. *Nature Human Behaviour* 3, 82–91. doi:10.1038/s41562-018-0474-5. Their decay runs over years since a work or person appeared; this project applies the same functional form to days after a news event.
