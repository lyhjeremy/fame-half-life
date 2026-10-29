# Fame Half-Life: long-form notes

These notes go with the [interactive page](https://lyhjeremy.github.io/fame-half-life/) and the [write-up](https://lyhjeremy.github.io/fame-half-life/overview/). Every number below is filled in from `results/summary.json` by `scripts/build_site.py`.

## Correction, 29 October 2026

Corrected 29 October 2026, after an independent audit. Three 2022 Nobel laureates in economics were missing because the Nobel Prize API gives the wrong year for that prize; they are now in. The curve comparison published on 28 October fitted only days above the baseline, which made a biexponential win almost by default (it reported 90%); every day now counts, and the selector was checked on simulated data. The half-life compared a smoothed series with a single raw day; it now compares like with like. 65 deaths reported days late are counted as delayed spikes rather than no spike. The Oscar baseline fell after the nominations; it now ends a week before them. Earlier figures are kept as sensitivity rows. Each change, with its reason, is in `docs/decisions.md` (entries 26 to 33).

## Question

When someone suddenly becomes news, how fast does the world stop looking them up? The data are daily English Wikipedia pageviews around deaths and major awards from 2016 to October 2025. Three things are measured: how fast the spike halves, which curve the fade follows, and whether attention settles back where it was.

## The event list

The rules were written in the spec and the list was committed to `data/events.csv` before any pageview was fetched.

- Deaths: humans with an English article, at least 30 Wikidata sitelinks and a day-precision date of death from 1 January 2016 to 31 October 2025. 1,995 candidates; 39 more were left out before that because their death date was not given to the day or conflicted.
- Awards: the six Nobel Prizes, the Academy Awards for the four acting categories and Best Director, the Ballon d'Or and the Booker Prize. 191 candidates.
- Excluded: article created less than 30 days before the event (21 deaths, 5 awards); award winners who died within a year (0).

At fetch time, 65 events were dropped because the article was moved to a new title inside the window, and 12 had a baseline under one view a day. That leaves 1,905 deaths and 178 awards (110 Nobel, 50 Academy Award, 9 Ballon d'Or, 9 Booker).

## Measures

Views are first divided by day-of-week factors from the baseline window (the median event's busiest weekday runs 1.42 times its quietest). Then, per event:

- baseline: median views, days -60 to -8 (median 202 a day for deaths, 73 for awards); for the Academy Awards, the 53 days ending 8 days before that year's nominations;
- peak: maximum of days 0 to +3;
- half-life: days from the smoothed peak until the centered 7-day mean of excess views falls below half of it;
- after week one: share of the first year's excess views that arrive more than 7 days after the peak;
- lift: median of days +335 to +365 divided by baseline.

A spike counts as visible when the peak is at least twice the baseline. 1,839 of 1,905 deaths have a visible spike (peak at least twice the baseline) on days 0 to 3. Another 65 (3.4%) have a delayed spike: nothing on days 0 to 3, then a day above twice the baseline on days 4 to 30 (Leonard Cohen, Sam Shepard and Steve Ditko among them), most often because the death became news days or weeks after it happened. 1 death has no spike at all.

## Results

### The fade

On the median death the page draws 206 times its usual traffic on the peak day, which is the day after the death in 44% of cases. Smoothed over a week, half the extra traffic is gone 2 days after the peak (middle half 2 to 3 days). The averaged curve loses nine tenths of its excess in 5 days and sits at 1.96 times baseline a month later and 1.09 times in the last month of the year, before jumping to 1.58 times on the anniversary. Awards lose nine tenths in 4 days, and climb again in the last week of the year as the next prize comes round. 1,839 of 1,905 deaths have a visible spike (peak at least twice the baseline) on days 0 to 3. Another 65 (3.4%) have a delayed spike: nothing on days 0 to 3, then a day above twice the baseline on days 4 to 30 (Leonard Cohen, Sam Shepard and Steve Ditko among them), most often because the death became news days or weeks after it happened. 1 death has no spike at all.

### The curve

Each event's daily views after the peak were fitted three ways, with every day counted: the baseline plus an exponential decay, plus a power law, or plus a biexponential (two exponentials, the form Candia et al. 2019 found over years in attention to songs, films and biographies). The biexponential has the lowest AIC for 76% of 1,839 deaths and 64% of 177 awards; the power law wins 14% of deaths and the exponential 9%. Where the biexponential wins, its fast part has a median time constant of 3.0 days and carries all but 1.8% of the initial excess; the slow part's median time constant is 169 days. On simulated series the selector names the true model 87% of the time for a pure exponential, 95% for a power law and 100% for a biexponential, and it calls 13% of pure exponentials biexponential, so the real share is a mild overstatement. The model comparison first published on 28 October dropped every day at or below the baseline before fitting; on the same simulations that method called 100% of pure exponentials biexponential, which is why it reported 90% biexponential wins.

### The aftermath

A year after a death the median page draws 1.08 times its old traffic, and 59% of pages sit above their baseline. Award winners settle at a median 4.20 times, but the prizes differ: Nobel laureates, with a median of 20 views a day beforehand, keep 8.81 times that; Booker winners 2.56; Ballon d'Or winners 0.87. For Academy Award winners the answer depends on which 'before' you use: against the 53 days ending a week before the nominations it is 0.58, against days -150 to -90 before the ceremony 1.03. Among deaths, each extra year of age at death goes with 2.0% less lift (p < 0.001), and pages that were busier beforehand gain less.

A regression of log lift on event type, log baseline, occupation group and year (OLS, HC3 errors, n = 2,083, R² = 0.28) puts awards 194% above deaths at the same prior traffic (p < 0.001); with the Oscar baseline as the spec defined it the figure is 167% above (p < 0.001). Among deaths, with age added (n = 1,902, R² = 0.33), each extra year of age at death goes with 2.0% less lift (p < 0.001). The same regression for log half-life explains little (R² = 0.09).

### Who lasts

Among deaths, the share of the first year's extra views that arrive after the first week runs from 23% (business) to 33% (writing and journalism), and median lift from 0.97 times (business) to 1.22 times (music). The gap between Nobel and Oscar winners is wider than any gap between occupations.

## Checks

Bot leakage: capping any day above 50 times the median of its six neighbors touches 31 events and leaves every half-life unchanged; median lift with the cap is 1.08 for deaths and 4.20 for awards. Renames: 65 events were dropped because the article moved to a new title inside the window, and 26 articles moved later are read under the title they had at the time. Peak window: searching for the peak over days 0 to 30 instead of 0 to 3 moves it later for 163 deaths and leaves the median half-life at 2 days. Smoothing and definition: the table below gives the half-life every way it was measured. Day of week: the median page's busiest weekday draws 1.42 times its quietest, which is why every series is adjusted before measuring.

## Limits

- English Wikipedia only; a view is a lookup, not a measure of how much anyone cares.
- The 30-sitelink floor is today's count and favors people known in many countries.
- Some automated traffic passes the `user` filter.
- Other news about the same person at the same time inflates the spike, and the data cannot separate it.
- Awards season raises an Oscar winner's traffic for months, so any "before" window is a choice: the Oscar lift is 0.58, 0.38 or 1.03 depending on it.
- The award sample is small, so differences between prizes are descriptive.
- The half-life as the spec first defined it compared a 7-day average with the single peak day, so it came out at one day for 95% of deaths. It now compares the smoothed series with its own smoothed peak (median 2 days); the old measure stays in the sensitivity table.

## Reference

Candia, C., Jara-Figueroa, C., Rodriguez-Sickert, C., Barabási, A.-L. and Hidalgo, C. A. (2019). The universal decay of collective memory and attention. *Nature Human Behaviour* 3, 82–91. doi:10.1038/s41562-018-0474-5. Their decay runs over years since a work or person appeared; this project applies the same functional form to days after a news event.
