# Data decisions

Choices the spec did not settle, recorded when they were made. Phase 0 entries were written before any pageview was fetched.

## Phase 0: the event list (frozen 2026-10-28)

1. **Death dates.** Only day-precision dates of death count, and deprecated Wikidata statements are skipped. 6 people whose date is given only to the month or year, and 33 whose item carries two different day-precision dates, are dropped before the list is written (`data/events_dropped_dates.json`).
2. **The sitelink floor is measured now.** Wikidata reports today's sitelink count, not the count on the day someone died. A person who gained articles in other languages after dying can clear the floor of 30 because of the death itself.
3. **"Created within 30 days before the event" includes articles created after it.** Either way no baseline exists. 26 events fall under this rule (21 deaths, 5 awards), among them George Floyd, Mahsa Amini and Li Wenliang, and Nobel laureates whose English article was written on the day of the prize.
4. **Award dates.** Nobel Prizes use `dateAwarded` from the Nobel Prize API (the announcement day). Academy Awards use the date of the ceremony item each win points to on Wikidata. The Ballon d'Or uses the ceremony date in the infobox of each year's English Wikipedia article, and the Booker Prize the announcement sentence in each year's article ("Man Booker Prize" up to 2018). The source is recorded per row in `date_source`.
5. **Ballon d'Or means the men's award.** The spec names "the Ballon d'Or"; the Ballon d'Or Féminin is a separate award and is not included. There was no award in 2020.
6. **The 2025 Booker Prize** was announced on 10 November 2025, after the window closes on 31 October 2025, so it is not in the list.
7. **Nobel Peace Prizes to organizations** are left out; only people count.
8. **Repeat winners** (Messi three times, Ronaldo, McDormand, Stone and Ali twice each) are separate events. Ronaldo's 2017 award falls inside the year after his 2016 one.
9. **People in both lists.** Seven Nobel laureates in the list have died since their prize, all more than a year after it, so their award events stay. Six of those deaths fall inside the window and are death events too.
10. **Occupation groups.** Each occupation on a person's Wikidata item is traced up the subclass tree to a fixed set of roots (`scripts/fetch_events.py`, `GROUPS`). A person takes the group of the first listed occupation that maps anywhere; an occupation reaching several roots takes the earliest group in this order: sport, politics and law, screen, music, writing and journalism, science and academia, business, visual arts and design, religion. Anyone unmatched is "other".
11. **Age at event** uses the earliest day-precision birth date; a birth date given only to the year is placed on 1 July, and to the month on the 15th.

## Phase 1: pageviews

12. **User-Agent.** Requests carry `fame-half-life/1.0 (https://github.com/lyhjeremy/fame-half-life; https://lyhjeremy.com)`. A first string ending in `python-urllib` was throttled with HTTP 429 within minutes; the run was stopped, the string changed, and the request gap raised to 0.5 seconds across all threads.
13. **Renames.** A page move leaves a revision whose summary reads "moved page [[A]] to [[B]]". Any such revision between day -60 and day +365 drops the event.
14. **Missing days.** The pageview API leaves out days with no views; those are filled with 0. Days after 27 October 2026, the last complete day on the fetch date, are left empty.

## Phase 2: measures and fits

15. **Day-of-week adjustment.** Factors are the mean views on each weekday in the baseline window divided by the window mean, clipped to 0.5 to 2 and rescaled to average 1. Every day's views are divided by its weekday's factor before any measure is taken.
16. **Half-life is counted from the peak day,** the day of most views in days 0 to +3, and is the number of days until the centered 7-day mean of excess views first falls below half the peak's excess.
17. **A visible spike** means peak views at least twice the baseline. Events below that have no half-life and no curve fit, and are counted as "no visible spike".
18. **Curve fits** use the days after the peak day up to day +365, on days where excess views are above zero (a log needs a positive number). An event needs 30 such days to be fitted. AIC is computed from the residual sum of squares of log excess, so each model is compared on the same days.
19. **The biexponential** is `A (w e^(-t/tau1) + (1 - w) e^(-t/tau2))`, the functional form of Candia et al. (2019), fitted by a fixed grid plus Nelder-Mead, so the browser can run the same code. It has four parameters against two for the exponential and the power law.
20. **Lift near the end of the window.** Events in the last days of October 2025 do not reach day +365 by 27 October 2026. Lift is computed when at least 21 of days +335 to +365 exist.
21. **Baseline under 1 view a day** leaves no ratio to compute; such events are dropped and counted.
22. **Bot check.** Any day above 50 times the median of its six neighbors (three each side) is cut to that bound, and every measure is recomputed.
