"""Validate raw histories and build a point-in-time feasibility cache, not a backtest."""

from collections import Counter, defaultdict
from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
sys.path.insert(0, str(ROOT / "models/strategy_search"))
from search import digest, first_trade, prior_price, readonly
from build_panel import DAY, Market, array, create_tables, normalize_trade, resolution_time, select_cohorts, write_csv
from releases import bea_releases, bls_releases, mapped_release, reference


def bucket_family(event, kind):
    if kind != "cpi":
        return kind
    series = {str(s["id"]) for s in event.get("series", [])}
    title = event["title"]
    if "Core CPI" in title:
        return "cpi_core_mom" if "MoM" in title else "cpi_core_yoy"
    if "10008" in series:
        return "cpi_headline_mom"
    if series & {"10007", "5"} and "Annual" in title:
        return "cpi_headline_yoy"
    return "cpi_threshold"


def load_metadata(root):
    official = bls_releases(root.glob("bls_batch_*.md"))
    official.update(bea_releases(root / "bea_schedules.md"))
    selected = json.loads((root / "discovery.json").read_text())["selected"]
    markets, releases, events = {}, {}, []
    for item in selected:
        event = item["event"]
        kind = bucket_family(event, item["family"])
        mapped = mapped_release(event, item["family"], official)
        row = {"family": kind, "event_id": str(event["id"]), "title": event["title"],
            "reference": reference(event, item["family"]), "gamma_end": event["endDate"],
            "release_utc": mapped["release_utc"] if mapped else "", "official_source": mapped["official_source"] if mapped else "",
            "markets": len(event["markets"]), "valid_markets": 0, "status": "mapped" if mapped else "no official release"}
        events.append(row)
        if kind == "cpi_threshold":
            row["status"] = "excluded non-bucket threshold"
            continue
        if not mapped:
            continue
        release_id = kind + ":" + mapped["reference"]
        stamp = int(datetime.fromisoformat(mapped["release_utc"]).timestamp())
        releases[release_id] = {**mapped, "family": kind, "release_id": release_id, "release_ts": stamp}
        for m in event["markets"]:
            prices = dict(zip(array(m["outcomes"]), map(float, array(m["outcomePrices"]))))
            if not m.get("closed") or set(prices) != {"Yes", "No"} or abs(sum(prices.values()) - 1) > .002:
                continue
            if min(abs(prices["Yes"]), abs(prices["Yes"] - 1)) > .001:
                continue
            resolved, basis = resolution_time(m)
            if resolved < stamp:
                continue
            tokens = dict(zip(array(m["outcomes"]), map(str, array(m["clobTokenIds"]))))
            mid = str(m["id"])
            market = Market(mid, release_id, release_id, m.get("groupItemTitle") or m["question"],
                m["conditionId"].lower(), tokens["Yes"], tokens["No"], stamp, resolved, basis,
                int(prices["Yes"] > .5), prices["Yes"], ())
            if mid in markets and markets[mid] != market:
                raise ValueError("Market belongs to conflicting release mappings")
            markets[mid] = market
            row["valid_markets"] += 1
    return markets, releases, events


def raw_fingerprint(root):
    paths = list((root / "trades").glob("*/summary.json")) + list((root / "trades").glob("*/page_*.json.gz"))
    paths += list(root.glob("bls_batch_*.md")) + [root / "bea_schedules.md", root / "discovery.json"]
    result = hashlib.sha256()
    for path in sorted(paths):
        result.update(str(path.relative_to(root)).encode())
        result.update(digest(path).encode())
    result.update(digest(FOLDER / "coverage.py").encode())
    result.update(digest(FOLDER / "releases.py").encode())
    return result.hexdigest()


def build_cache(root, markets, events):
    path = root / "trades.sqlite3"
    fingerprint = raw_fingerprint(root)
    if path.exists():
        with readonly(path) as db:
            if db.execute("SELECT fingerprint FROM build").fetchone()[0] != fingerprint:
                raise ValueError("Macro source fingerprint changed")
        return path
    temporary = path.with_suffix(".building")
    if temporary.exists():
        raise ValueError("Incomplete macro cache; inspect before resuming")
    raw_count = 0
    raw_wallets, raw_totals = defaultdict(set), Counter()
    selected = json.loads((root / "discovery.json").read_text())["selected"]
    conditions = {str(i['event']['id']): {m['conditionId'].lower() for m in i['event']['markets']} for i in selected}
    with sqlite3.connect(temporary) as db:
        create_tables(db, markets)
        for event in events:
            folder = root / "trades" / event["event_id"]
            summary = json.loads((folder / "summary.json").read_text())
            if summary["status"] != "exhausted":
                raise ValueError("Partial collection cannot enter feasibility")
            pages = sorted(folder.glob("page_*.json.gz"))
            if len(pages) != summary["pages"]:
                raise ValueError("Page count mismatch")
            members = {m.condition_id: m for m in markets.values() if m.meeting == event["family"] + ":" + event["reference"]}
            cursor, count = None, 0
            for page in pages:
                envelope = json.loads(gzip.decompress(page.read_bytes()))
                if envelope["request_cursor"] != cursor:
                    raise ValueError("Broken trade cursor chain")
                response = envelope["response"]
                for record in response['data']:
                    if record['condition_id'].lower() not in conditions[event['event_id']]:
                        raise ValueError("Raw trade belongs to another Gamma event")
                    raw_wallets[event['family']].add(record['proxy_wallet'].lower())
                raw_totals[event['family']] += len(response['data'])
                count += len(response["data"])
                trades = [normalize_trade(r, members[r["condition_id"].lower()]) for r in response["data"]
                          if r["condition_id"].lower() in members]
                db.executemany("INSERT OR IGNORE INTO trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                               [tuple(t.__dict__.values()) for t in trades])
                cursor = response["pagination"]["next_cursor"]
            if cursor is not None or count != summary["participant_rows"]:
                raise ValueError("Unexhausted or inconsistent raw history")
            event.update({"participant_rows": count, "wallets": summary["distinct_wallets"],
                "earliest_trade": summary["earliest_trade"] or "", "latest_trade": summary["latest_trade"] or "",
                "pages": len(pages)})
            raw_count += count
            db.commit()
        db.execute("CREATE INDEX market_time ON trades(market_id, ts)")
        db.execute("CREATE INDEX token_time ON trades(market_id, token_outcome, ts)")
        db.execute("INSERT INTO build VALUES (?,?,?)", (fingerprint, raw_count, db.execute("SELECT COUNT(*) FROM trades").fetchone()[0]))
    temporary.replace(path)
    write_csv(FOLDER / "raw_coverage.csv", [{'family': f, 'participant_rows': raw_totals[f],
        'distinct_wallets': len(ws)} for f, ws in sorted(raw_wallets.items())])
    return path


def attach_fomc(db, root):
    db.execute("ATTACH DATABASE ? AS fomc", (str(root.parent / "wallet_backtest_cache/trades.sqlite3"),))


def skill(db, family, cutoff, score=True):
    rows = db.execute("""SELECT wallet, SUM(n), SUM(pnl), SUM(gross) FROM (
        SELECT t.wallet, COUNT(*) n, SUM(t.signed_yes_shares*(m.realized-t.price)) pnl, SUM(t.notional) gross
        FROM fomc.trades t JOIN fomc.markets m USING(market_id)
        WHERE m.resolved_ts<? AND t.ts<? GROUP BY t.wallet
        UNION ALL
        SELECT t.wallet, COUNT(*) n, SUM(t.signed_yes_shares*(m.realized-t.price)) pnl, SUM(t.notional) gross
        FROM main.trades t JOIN main.markets m USING(market_id)
        WHERE m.event_id LIKE ? AND m.resolved_ts<? AND t.ts<? GROUP BY t.wallet
        ) GROUP BY wallet HAVING SUM(n)>=5 AND SUM(gross)>0""", (cutoff, cutoff, family + ":%", cutoff, cutoff)).fetchall()
    return {wallet: {"score": pnl / gross * n / (n + 20) if score else 0., "n_trades": n} for wallet, n, pnl, gross in rows}


def qualifying_counts(db, requests):
    stream = iter(db.execute("""SELECT wallet, eligible, notional, family FROM (
        SELECT t.wallet, MAX(m.resolved_ts,t.ts) eligible, t.notional, 'fomc' family
        FROM fomc.trades t JOIN fomc.markets m USING(market_id)
        UNION ALL
        SELECT t.wallet, MAX(m.resolved_ts,t.ts), t.notional,
            SUBSTR(m.event_id,1,INSTR(m.event_id,':')-1)
        FROM main.trades t JOIN main.markets m USING(market_id)
        ) ORDER BY eligible"""))
    current = next(stream, None)
    counts, gross = defaultdict(Counter), defaultdict(Counter)
    result = {}
    for family, cutoff in sorted(set(requests), key=lambda r: (r[1], r[0])):
        while current is not None and current[1] < cutoff:
            wallet, _, notional, source = current
            counts[source][wallet] += 1
            gross[source][wallet] += notional
            current = next(stream, None)
        wallets = counts['fomc'].keys() | counts[family].keys()
        result[(family, cutoff)] = sum(counts['fomc'][w] + counts[family][w] >= 5
            and gross['fomc'][w] + gross[family][w] > 0 for w in wallets)
    return result


def feasibility(root):
    markets, releases, events = load_metadata(root)
    cache = build_cache(root, markets, events)
    for row in events:
        summary = json.loads((root / "trades" / row["event_id"] / "summary.json").read_text())
        row.update({"participant_rows": summary["participant_rows"], "wallets": summary["distinct_wallets"],
            "earliest_trade": summary["earliest_trade"] or "", "latest_trade": summary["latest_trade"] or "", "pages": summary["pages"]})
    coverage = []
    with readonly(cache) as db:
        attach_fomc(db, root)
        qualifying = qualifying_counts(db, [(r['family'], r['release_ts'] - d * DAY)
            for r in releases.values() for d in (3, 1)])
        for rid, info in sorted(releases.items()):
            members = [m for m in markets.values() if m.meeting == rid]
            row = {"family": info["family"], "release_id": rid, "reference": info["reference"],
                "release_utc": info["release_utc"], "official_source": info["official_source"],
                "event_objects": sum(e["family"] == info["family"] and e["reference"] == info["reference"] for e in events),
                "valid_markets": len(members)}
            for days in (3, 1):
                cutoff = info["release_ts"] - days * DAY
                n_smart = qualifying[(info["family"], cutoff)] // 10
                eligible = sum(all(first_trade(db, m.market_id, side, cutoff, info["release_ts"]) for side in ("YES", "NO"))
                               and prior_price(db, m.market_id, cutoff) is not None for m in members)
                row[f"eligible_markets_t{days}"] = eligible
                row[f"n_smart_t{days}"] = n_smart
            row["usable"] = bool(row["valid_markets"] and all(row[f"eligible_markets_t{d}"] and row[f"n_smart_t{d}"] >= 20 for d in (3, 1)))
            coverage.append(row)
            print(rid, row['usable'], flush=True)
    write_csv(FOLDER / "event_inventory.csv", events)
    write_csv(FOLDER / "release_coverage.csv", coverage)
    summary = []
    for kind in ("cpi_headline_mom", "cpi_headline_yoy", "cpi_core_mom", "cpi_core_yoy",
                 "cpi_threshold", "payrolls", "unemployment", "pce", "gdp"):
        es = [e for e in events if e["family"] == kind]
        rs = [r for r in coverage if r["family"] == kind]
        usable = sum(r["usable"] for r in rs)
        summary.append({"family": kind, "gamma_event_objects": len(es), "official_releases": len(rs),
            "usable_releases": usable, "markets": sum(e["markets"] for e in es),
            "participant_rows": sum(e["participant_rows"] for e in es),
            "sum_event_wallet_counts": sum(e["wallets"] for e in es), "included": usable >= 15})
    write_csv(FOLDER / "family_coverage.csv", summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    feasibility(Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "data/polymarket/macro")
