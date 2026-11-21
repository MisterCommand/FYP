"""Collect fresh October history with the approved external collector, without computing returns."""

import argparse
import importlib.util
import json
from pathlib import Path
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path.home() / "data/polymarket")
    args = parser.parse_args()
    root = args.data_root.resolve()
    spec = importlib.util.spec_from_file_location("collector", root / "feasibility/collect_meetings.py")
    collector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(collector)
    output = root / "strategy_search/fresh"
    output.mkdir(parents=True, exist_ok=True)
    event = collector.fetch("https://gamma-api.polymarket.com/events/606422")
    if not event["closed"] or not event["endDate"].startswith("2026-10-29"):
        raise ValueError("Fresh event is not the expected resolved October meeting")
    (output / "event.json").write_text(json.dumps(event, indent=2) + "\n")
    mapping = []
    for market in event["markets"]:
        if not market["closed"]:
            raise ValueError("Fresh market is unresolved")
        mapping.append({"meeting_month": "2026-10", "event_id": str(event["id"]),
            "market_id": str(market["id"]), "outcome": market["groupItemTitle"],
            "condition_id": market["conditionId"].lower(), "tokens": market["clobTokenIds"],
            "start_date": market.get("startDate"), "created_at": market.get("createdAt")})
    collector.MAPPING = mapping
    collector.OUTPUT = output
    collector.DEADLINE = time.monotonic() + 1200
    summary = collector.collect(str(event["id"]))
    if summary["status"] != "exhausted":
        raise ValueError("Fresh history did not exhaust; do not evaluate partial collection")
    print("Fresh history available; no performance statistics calculated.", flush=True)


if __name__ == "__main__":
    main()
