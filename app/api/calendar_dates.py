"""Scheduled FOMC decision dates, federalreserve.gov monetary policy calendars.

The research scripts provide meeting months, not decision dates.
"""

DATES = {
    2023: "02-01 03-22 05-03 06-14 07-26 09-20 11-01 12-13",
    2024: "01-31 03-20 05-01 06-12 07-31 09-18 11-07 12-18",
    2025: "01-29 03-19 05-07 06-18 07-30 09-17 10-29 12-10",
    2026: "01-28 03-18 04-29 06-17 07-29 09-16 10-28 12-09",
}
MEETINGS = {f"{year}-{day[:2]}": f"{year}-{day}"
            for year, days in DATES.items() for day in days.split()}
