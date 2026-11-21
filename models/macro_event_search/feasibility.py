"""Discover and collect macro market coverage without computing strategy performance."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlencode

TERMS = ("inflation", "CPI", "jobs added", "unemployment", "PCE", "GDP")
MONTHS = "January February March April May June July August September October November December".split()


def family(event):
    title = event["title"]
    series = {str(s["id"]) for s in event.get("series", [])}
    if series & {"10007", "10008", "11905", "12054", "5"} or re.match(
            r"^(?:US inflation|What will US inflation|Core CPI|\w+ Inflation US -)", title, re.I):
        return "cpi"
    if re.fullmatch(r"How many jobs added in \w+\?", title):
        return "payrolls"
    if re.fullmatch(r"(?:" + "|".join(MONTHS) + r") Unemployment Rate", title):
        return "unemployment"
    if re.match(r"^Core PCE (?:MoM|YoY) -", title):
        return "pce"
    if re.fullmatch(r"US GDP growth in Q[1-4] 20\d\d\?", title):
        return "gdp"
    return None


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def load_collector(root):
    path = root.parent / "feasibility/collect_meetings.py"
    spec = importlib.util.spec_from_file_location("macro_collector", path)
    collector = importlib.util.module_from_spec(spec)
    args = sys.argv
    try:
        sys.argv = [str(path)]
        spec.loader.exec_module(collector)
    finally:
        sys.argv = args
    return collector


def discover(root, collector):
    folder = root / "gamma"
    folder.mkdir(exist_ok=True)
    events = {}
    for term in TERMS:
        page, previous = 1, set()
        while True:
            path = folder / f"{term.replace(' ', '_')}_{page:03d}.json"
            if not path.exists():
                result = collector.fetch("https://gamma-api.polymarket.com/public-search?" + urlencode({
                    "q": term, "limit_per_type": 50, "page": page, "keep_closed_markets": 1,
                    "search_tags": "false", "search_profiles": "false"}))
                save(path, result)
            result = json.loads(path.read_text())
            batch = {str(e["id"]): e for e in result.get("events", [])}
            if previous and not (set(batch) - previous) and result.get("pagination", {}).get("hasMore"):
                raise ValueError("Search pagination made no progress")
            previous.update(batch)
            events.update(batch)
            if not result.get("pagination", {}).get("hasMore"):
                break
            page += 1
        print("Search exhausted:", term, len(previous), "events", page, "pages", flush=True)
    now = datetime.now(timezone.utc)
    floor = now.replace(year=now.year - 3)
    selected = []
    for event in events.values():
        kind = family(event)
        if not kind or not event.get("closed") or not event.get("endDate"):
            continue
        end = datetime.fromisoformat(event["endDate"].replace("Z", "+00:00"))
        if not floor <= end <= now:
            continue
        path = folder / ("event_" + str(event["id"]) + ".json")
        if not path.exists():
            save(path, collector.fetch("https://gamma-api.polymarket.com/events/" + str(event["id"])))
        full = json.loads(path.read_text())
        selected.append({"family": kind, "event": full})
    save(root / "discovery.json", {"as_of": now.isoformat(), "retention_floor": floor.isoformat(),
        "selected": selected, "all_search_events": len(events)})
    print("Resolved candidate event objects:", dict(Counter(r["family"] for r in selected)), flush=True)
    return selected


def mapping(selected):
    rows = []
    for item in selected:
        event = item["event"]
        for m in event["markets"]:
            outcomes = json.loads(m["outcomes"]) if isinstance(m["outcomes"], str) else m["outcomes"]
            if set(outcomes) != {"Yes", "No"}:
                raise ValueError("Non-binary market requires explicit mapping")
            rows.append({"event_id": str(event["id"]), "market_id": str(m["id"]),
                "meeting_month": item["family"] + ":" + str(event["id"]),
                "outcome": m.get("groupItemTitle") or m["question"],
                "condition_id": m["conditionId"], "tokens": m["clobTokenIds"],
                "start_date": m.get("startDate", ""), "created_at": m.get("createdAt", "")})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("discover", "collect"))
    parser.add_argument("--data-root", type=Path, default=Path.home() / "data/polymarket/macro")
    args = parser.parse_args()
    root = args.data_root.resolve()
    if root.is_relative_to(Path(__file__).resolve().parents[2]):
        parser.error("Raw data must remain outside the repository")
    root.mkdir(parents=True, exist_ok=True)
    collector = load_collector(root)
    if args.phase == "discover":
        discover(root, collector)
        return
    selected = json.loads((root / "discovery.json").read_text())["selected"]
    collector.MAPPING = mapping(selected)
    collector.OUTPUT = root / "trades"
    collector.OUTPUT.mkdir(exist_ok=True)
    collector.DEADLINE = time.monotonic() + 7200
    with ThreadPoolExecutor(max_workers=4) as pool:
        summaries = list(pool.map(collector.collect, sorted({r["event_id"] for r in collector.MAPPING})))
    counts = Counter(r["status"] for r in summaries)
    print("Collection status:", dict(counts), flush=True)
    if set(counts) != {"exhausted"}:
        raise SystemExit("Incomplete histories: inspect summaries before any eligibility decision")


if __name__ == "__main__":
    main()
