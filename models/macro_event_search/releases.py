"""Official release-time mapping; market end dates are not release timestamps."""

from datetime import datetime, timezone
from pathlib import Path
import re
from zoneinfo import ZoneInfo

MONTHS = "January February March April May June July August September October November December".split()
MONTH_PATTERN = "(?:" + "|".join(MONTHS) + ")"


def release_utc(date, clock="08:30 AM"):
    local = datetime.strptime(date + " " + clock, "%Y-%m-%d %I:%M %p")
    return local.replace(tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)


def bls_releases(paths):
    releases = {}
    for path in paths:
        for page in re.split(r"(?=## Page \d+:)", Path(path).read_text()):
            url = re.search(r"URL: (https://www.bls.gov/schedule/(\d{4})/(\d{2})_sched.htm)", page)
            if not url:
                continue
            year, month = int(url[2]), int(url[3])
            rows = [line for line in page.splitlines() if re.match(r"\| \d", line)]
            for index, row in enumerate(rows):
                for cell in row.strip("|").split("|"):
                    day = int(re.match(r"\s*(\d+)", cell)[1])
                    if (index == 0 and day > 14) or (index >= 4 and day < 8):
                        continue
                    for match in re.finditer(r"(Consumer Price Index|Employment Situation) (" + MONTH_PATTERN +
                            r") (\d{4}) (\d{2}:\d{2} [AP]M)", cell):
                        kind = "cpi" if match[1] == "Consumer Price Index" else "employment"
                        reference = f"{int(match[3]):04d}-{MONTHS.index(match[2]) + 1:02d}"
                        value = {"release_utc": release_utc(f"{year:04d}-{month:02d}-{day:02d}", match[4]).isoformat(),
                                 "official_source": url[1], "reference": reference}
                        key = (kind, reference)
                        if key in releases and releases[key]["release_utc"] != value["release_utc"]:
                            raise ValueError("Conflicting official release dates")
                        releases[key] = value
    return releases


def bea_releases(path):
    result = {}
    for page in re.split(r"(?=## Page \d+:)", Path(path).read_text()):
        source = re.search(r"URL: (\S+)", page)
        year = re.search(r"\| Year (\d{4})", page)
        if not source or not year:
            continue
        for row in page.splitlines():
            if not row.startswith("|"):
                continue
            cells = [c.strip() for c in row.strip("|").split("|")]
            date = re.fullmatch(r"(" + MONTH_PATTERN + r") (\d+) (\d+:\d+ [AP]M)", cells[0])
            if not date:
                continue
            title = cells[2]
            ref = re.search(r"Personal Income and Outlays, (" + MONTH_PATTERN + r") (\d{4})", title)
            if ref:
                key = ("pce", f"{ref[2]}-{MONTHS.index(ref[1]) + 1:02d}")
            else:
                quarter = re.search(r"([1-4])(?:st|nd|rd|th) Quarter(?: and Year)? (\d{4})", title)
                if not quarter or not re.search(r"Advance Estimate|Initial Estimate", title):
                    continue
                key = ("gdp", f"{quarter[2]}-Q{quarter[1]}")
            stamp = release_utc(f"{year[1]}-{MONTHS.index(date[1])+1:02d}-{int(date[2]):02d}", date[3])
            result[key] = {"release_utc": stamp.isoformat(), "reference": key[1], "official_source": source[1]}
    return result


def reference(event, family):
    title = event["title"]
    if family == "gdp":
        match = re.search(r"Q([1-4]) (\d{4})", title)
        return f"{match[2]}-Q{match[1]}"
    if family == "cpi":
        explicit = re.search(r"BLS (" + MONTH_PATTERN + r") (\d{4}) Consumer Price Index report", event.get("description", ""))
        if explicit:
            return f"{explicit[2]}-{MONTHS.index(explicit[1])+1:02d}"
    months = re.findall(MONTH_PATTERN, title)
    if not months:
        raise ValueError("Reference month not found")
    month = MONTHS.index(months[-1]) + 1
    years = re.findall(r"20\d{2}", title)
    end = datetime.fromisoformat(event["endDate"].replace("Z", "+00:00"))
    year = int(years[-1]) if years else end.year - int(month > end.month)
    return f"{year:04d}-{month:02d}"


def mapped_release(event, family, official):
    ref = reference(event, family)
    kind = "employment" if family in ("payrolls", "unemployment") else family
    return official.get((kind, ref))
