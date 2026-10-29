# Fame Half-Life: long-form notes

These notes go with the [interactive page](https://lyhjeremy.github.io/fame-half-life/) and the [write-up](https://lyhjeremy.github.io/fame-half-life/overview/). Every number below is filled in from `results/summary.json` by `scripts/build_site.py`.

## Question

When someone suddenly becomes news, how fast does the world stop looking them up? The data are daily English Wikipedia pageviews around deaths and major awards from 2016 to October 2025. Three things are measured: how fast the spike halves, which curve the fade follows, and whether attention settles back where it was.

## The event list

The rules were written in the spec and the list was committed to `data/events.csv` before any pageview was fetched.

- Deaths: humans with an English article, at least 30 Wikidata sitelinks and a day-precision date of death from 1 January 2016 to 31 October 2025. {{nDeathCand}} candidates; {{nDropDates}} more were left out before that because their death date was not given to the day or conflicted.
- Awards: the six Nobel Prizes, the Academy Awards for the four acting categories and Best Director, the Ballon d'Or and the Booker Prize. {{nAwardCand}} candidates.
- Excluded: article created less than 30 days before the event ({{nCreatedDeath}} deaths, {{nCreatedAward}} awards); award winners who died within a year ({{nAwardDied}}).

At fetch time, {{nRenamed}} events were dropped because the article was moved to a new title inside the window, and {{nNoBase}} had a baseline under one view a day. That leaves {{nDeaths}} deaths and {{nAwards}} awards ({{nNobel}} Nobel, {{nOscar}} Academy Award, {{nBallon}} Ballon d'Or, {{nBooker}} Booker).

## Measures

Views are first divided by day-of-week factors from the baseline window (the median event's busiest weekday runs {{dowAmp}} times its quietest). Then, per event:

- baseline: median views, days -60 to -8 (median {{deathBase}} a day for deaths, {{awardBase}} for awards);
- peak: maximum of days 0 to +3;
- half-life: days from the peak until the centered 7-day mean of excess views falls below half the peak excess;
- after week one: share of the first year's excess views that arrive more than 7 days after the peak;
- lift: median of days +335 to +365 divided by baseline.

A spike counts as visible when the peak is at least twice the baseline. {{deathNoSpike}}% of deaths and {{awardNoSpike}}% of awards have none.

## Results

{{writeupResults}}

## Checks

{{checksText}}

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
