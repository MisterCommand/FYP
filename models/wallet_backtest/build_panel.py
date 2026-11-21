"""Frozen, point-in-time FOMC wallet signals; no probability model is fitted."""

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import gzip
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import re
import runpy
import sqlite3


ROOT = Path(__file__).resolve().parents[2]
CUTOFF_DAYS = (7, 3, 1)
MIN_TRADES = 5
SHRINK_TRADES = 20
SMART_FRACTION = 0.1
MIN_SMART = 20
SEED = 42
DAY = 86400


def timestamp(value):
    day = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if day.tzinfo is None:
        raise ValueError("Timestamp must have an explicit UTC offset")
    return int(day.timestamp())


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def array(value):
    return json.loads(value) if isinstance(value, str) else value


def resolution_time(metadata):
    times, bases = [], []
    for key in ("closedTime", "umaEndDate"):
        value = metadata.get(key)
        if not value:
            continue
        if re.fullmatch(r"[A-Za-z]+ \d{1,2}, \d{4}", value):
            day = datetime.strptime(value, "%B %d, %Y").replace(tzinfo=timezone.utc)
            times.append(int((day + timedelta(days=1)).timestamp()))
            bases.append(key + "_day_upper_bound")
        else:
            times.append(timestamp(value))
            bases.append(key)
    if not times:
        raise ValueError("No resolution timestamp proxy")
    return max(times), "+".join(bases)


@dataclass(frozen=True)
class Market:
    market_id: str
    event_id: str
    meeting: str
    outcome: str
    condition_id: str
    yes_token: str
    no_token: str
    decision_ts: int
    resolved_ts: int
    resolution_basis: str
    realized: int
    gamma_yes: float
    quotes: tuple


def load_markets(probabilities, gamma_dir, calendar):
    grouped = {}
    with Path(probabilities).open() as handle:
        for row in csv.DictReader(handle):
            if not all(re.fullmatch(r"\d+", row[key]) for key in ("market_id", "event_id")):
                raise ValueError("Market and event IDs must be digit strings")
            grouped.setdefault(row["market_id"], []).append(row)
    markets = {}
    for market_id, rows in grouped.items():
        first = rows[0]
        for key in ("event_id", "meeting_month", "outcome", "final_outcome"):
            if len({r[key] for r in rows}) != 1:
                raise ValueError(f"Inconsistent {key} for market {market_id}")
        metadata = json.loads((Path(gamma_dir) / f"{market_id}.json").read_text())
        if str(metadata["id"]) != market_id or not metadata.get("closed"):
            raise ValueError(f"Gamma ID/closed status mismatch for {market_id}")
        outcomes = array(metadata["outcomes"])
        tokens = dict(zip(outcomes, map(str, array(metadata["clobTokenIds"]))))
        if set(tokens) != {"Yes", "No"} or tokens["Yes"] == tokens["No"]:
            raise ValueError(f"Invalid Gamma token mapping for {market_id}")
        prices = dict(zip(outcomes, map(Decimal, array(metadata["outcomePrices"]))))
        realized = int(first["final_outcome"])
        if realized not in (0, 1) or any(abs(prices[key] - target) > Decimal("0.0001")
                for key, target in (("Yes", realized), ("No", 1 - realized))):
            raise ValueError(f"Gamma settlement disagrees with CSV for {market_id}")
        resolved_ts, resolution_basis = resolution_time(metadata)
        quotes = []
        for row in rows:
            p = float(row["market_probability"])
            if not math.isfinite(p) or not 0 <= p <= 1:
                raise ValueError("Invalid market probability")
            quotes.append((timestamp(row["date"]), p))
        if len(dict(quotes)) != len(quotes):
            raise ValueError(f"Duplicate probability timestamp for {market_id}")
        markets[market_id] = Market(
            market_id, first["event_id"], first["meeting_month"],
            first["outcome"].replace("no change", "No change"), metadata["conditionId"].lower(),
            tokens["Yes"], tokens["No"], timestamp(calendar[first["meeting_month"]] + "T00:00:00Z"),
            resolved_ts, resolution_basis, realized, float(prices["Yes"]), tuple(sorted(quotes)))
    for event_id in {m.event_id for m in markets.values()}:
        meeting = [m for m in markets.values() if m.event_id == event_id]
        if len({m.decision_ts for m in meeting}) != 1 or sum(m.realized for m in meeting) != 1:
            raise ValueError(f"Inconsistent meeting or settlement labels for event {event_id}")
    return markets


@dataclass(frozen=True)
class Trade:
    dedup_key: bytes
    market_id: str
    wallet: str
    ts: int
    transaction_hash: str
    token_outcome: str
    side: str
    shares: float
    raw_price: float
    signed_yes_shares: float
    price: float
    notional: float
    signed_yes_notional: float


def normalize_trade(record, market):
    if record["condition_id"].lower() != market.condition_id:
        raise ValueError("Trade condition does not match market")
    token = str(record["token_id"])
    if token not in (market.yes_token, market.no_token):
        raise ValueError("Trade token does not match Gamma")
    yes = token == market.yes_token
    side = record["side"].upper()
    shares, raw_price = Decimal(str(record["size"])), Decimal(str(record["price"]))
    if side not in ("BUY", "SELL") or not shares.is_finite() or not raw_price.is_finite() or shares <= 0 or not 0 <= raw_price <= 1:
        raise ValueError("Invalid trade amounts or side")
    wallet, tx = record["proxy_wallet"].lower(), record["transaction_hash"].lower()
    if not re.fullmatch(r"0x[0-9a-f]{40}", wallet) or not re.fullmatch(r"0x[0-9a-f]{64}", tx):
        raise ValueError("Invalid wallet or transaction hash")
    ts = int(record["timestamp"])
    if ts != record["timestamp"] or ts < 0:
        raise ValueError("Invalid trade timestamp")
    direction = (1 if side == "BUY" else -1) * (1 if yes else -1)
    key = [market.market_id, tx, wallet, token, side, ts,
           str(shares.normalize()), str(raw_price.normalize())]
    dedup_key = hashlib.sha256(json.dumps(key, separators=(",", ":")).encode()).digest()
    notional = shares * raw_price
    return Trade(dedup_key, market.market_id, wallet, ts, tx, "YES" if yes else "NO", side,
                 float(shares), float(raw_price), float(shares * direction),
                 float(raw_price if yes else 1 - raw_price), float(notional), float(direction * notional))


def settlement_pnl(signed_yes_shares, price, settlement):
    return signed_yes_shares * (settlement - price)


def create_tables(db, markets):
    db.executescript("""
        CREATE TABLE markets (market_id TEXT PRIMARY KEY, event_id TEXT, outcome TEXT,
                              resolved_ts INTEGER, realized INTEGER);
        CREATE TABLE trades (dedup_key BLOB PRIMARY KEY, market_id TEXT, wallet TEXT, ts INTEGER,
            transaction_hash TEXT, token_outcome TEXT, side TEXT, shares REAL, raw_price REAL,
            signed_yes_shares REAL, price REAL, notional REAL, signed_yes_notional REAL);
        CREATE VIEW wallet_trades AS SELECT t.*, m.outcome, m.event_id FROM trades t
            JOIN markets m USING (market_id);
        CREATE TABLE build (fingerprint TEXT, raw_rows INTEGER, deduplicated_rows INTEGER);
    """)
    meeting_resolution = {m.event_id: max(x.resolved_ts for x in markets.values() if x.event_id == m.event_id)
                          for m in markets.values()}
    db.executemany("INSERT INTO markets VALUES (?, ?, ?, ?, ?)",
                   [(m.market_id, m.event_id, m.outcome, meeting_resolution[m.event_id], m.realized)
                    for m in markets.values()])


def source_fingerprint(data_root, probabilities, calendar_path, markets):
    paths = [Path(__file__), probabilities, calendar_path, data_root / "meeting_history/SHA256SUMS"]
    for market in markets.values():
        paths.append(data_root / f"feasibility/gamma/{market.market_id}.json")
    for event_id in {m.event_id for m in markets.values()}:
        paths.extend(data_root / f"meeting_history/{event_id}/{name}" for name in ("summary.json", "config.json"))
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def build_cache(data_root, cache_path, markets, fingerprint):
    if cache_path.exists():
        with sqlite3.connect(cache_path) as db:
            row = db.execute("SELECT * FROM build").fetchone()
            if row and row[0] == fingerprint:
                return row[1], row[2]
        raise ValueError("Cache fingerprint changed; use another --cache path or remove the old external cache")
    temporary = cache_path.with_suffix(".building.sqlite3")
    if temporary.exists():
        raise ValueError(f"Incomplete cache exists: {temporary}; inspect/remove it before restarting")
    by_condition = {m.condition_id: m for m in markets.values()}
    hashes = {}
    for line in (data_root / "meeting_history/SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        hashes[name] = digest
    raw_rows = 0
    db = sqlite3.connect(temporary)
    try:
        create_tables(db, markets)
        for event_id in sorted({m.event_id for m in markets.values()}):
            folder = data_root / "meeting_history" / event_id
            summary = json.loads((folder / "summary.json").read_text())
            if summary["status"] != "exhausted":
                raise ValueError(f"Incomplete raw collection for event {event_id}")
            cursor, count = None, 0
            pages = sorted(folder.glob("page_*.json.gz"))
            if len(pages) != summary["pages"]:
                raise ValueError("Raw page count does not match summary")
            for page in pages:
                compressed = page.read_bytes()
                if hashlib.sha256(compressed).hexdigest() != hashes[str(page.relative_to(data_root / "meeting_history"))]:
                    raise ValueError(f"Raw page checksum mismatch: {page}")
                envelope = json.loads(gzip.decompress(compressed))
                if envelope["request_cursor"] != cursor:
                    raise ValueError("Broken raw cursor chain")
                response = envelope["response"]
                trades = []
                for record in response["data"]:
                    market = by_condition[record["condition_id"].lower()]
                    if market.event_id != event_id:
                        raise ValueError("Raw trade belongs to another meeting")
                    trades.append(tuple(normalize_trade(record, market).__dict__.values()))
                db.executemany("INSERT OR IGNORE INTO trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", trades)
                count += len(trades)
                cursor = response["pagination"]["next_cursor"]
            if cursor is not None or count != summary["participant_rows"]:
                raise ValueError("Raw collection does not match summary")
            raw_rows += count
            db.commit()
            print(f"Ingested event {event_id}: {count:,} participant rows", flush=True)
        dedup_rows = db.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        db.execute("CREATE INDEX trades_market_ts ON trades(market_id, ts)")
        db.execute("ANALYZE")
        db.execute("INSERT INTO build VALUES (?, ?, ?)", (fingerprint, raw_rows, dedup_rows))
        db.commit()
    finally:
        db.close()
    temporary.replace(cache_path)
    return raw_rows, dedup_rows


def wallet_scores(db, cutoff):
    rows = db.execute("""
        SELECT t.wallet, COUNT(*), SUM(t.signed_yes_shares * (m.realized - t.price)), SUM(t.notional)
        FROM trades t JOIN markets m USING (market_id)
        WHERE m.resolved_ts < ? AND t.ts < ?
        GROUP BY t.wallet HAVING COUNT(*) >= ? AND SUM(t.notional) > 0
        """, (cutoff, cutoff, MIN_TRADES)).fetchall()
    return {wallet: {"n_trades": n, "pnl": pnl, "notional": notional,
                     "score": pnl / notional * n / (n + SHRINK_TRADES)}
            for wallet, n, pnl, notional in rows}


def select_cohorts(scores, event_id, cutoff, seed=SEED):
    ranked = sorted(scores, key=lambda wallet: (-scores[wallet]["score"], wallet))
    n = math.floor(len(ranked) * SMART_FRACTION)
    if n < MIN_SMART:
        return None, None
    smart = set(ranked[:n])
    placebo = set(random.Random(f"{seed}:{event_id}:{cutoff}").sample(sorted(scores), n))
    return smart, placebo


def window_flows(db, market_id, cutoff):
    return db.execute("""
        SELECT wallet, SUM(signed_yes_notional), SUM(notional), COUNT(*) FROM trades
        WHERE market_id = ? AND ts >= ? AND ts < ? GROUP BY wallet
        """, (market_id, cutoff - 7 * DAY, cutoff)).fetchall()


def aggregate_flow(flows, members=None):
    selected = [row for row in flows if members is None or row[0] in members]
    net = math.fsum(row[1] for row in selected)
    gross = math.fsum(row[2] for row in selected)
    signal = max(-1., min(1., net / gross)) if gross else 0.
    return {"signal": signal, "net_yes_notional": net, "gross_notional": gross,
            "n_trades": sum(row[3] for row in selected), "n_wallets": len(selected)}


def probability_at(market, cutoff):
    available = [(ts, p) for ts, p in market.quotes if ts <= cutoff]
    return available[-1] if available else (None, None)


def retention_floor(data_root, event_id):
    folder = data_root / "meeting_history" / event_id
    first_page = sorted(folder.glob("page_*.json.gz"))[0]
    with gzip.open(first_page, "rt") as handle:
        acquired = datetime.fromisoformat(json.load(handle)["collected_at_utc"])
    day = 28 if acquired.month == 2 and acquired.day == 29 else acquired.day
    return int(acquired.replace(year=acquired.year - 3, day=day).timestamp())


def write_csv(path, rows):
    if not rows:
        raise ValueError("Cannot write empty derived table")
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build_panel(db, markets, floors, seed=SEED):
    panel, cohorts = [], []
    events = sorted({(m.decision_ts, m.event_id, m.meeting) for m in markets.values()})
    for decision, event_id, meeting in events:
        for days in CUTOFF_DAYS:
            cutoff = decision - days * DAY
            scores = wallet_scores(db, cutoff)
            smart, placebo = select_cohorts(scores, event_id, cutoff, seed)
            n_smart = len(smart) if smart is not None else 0
            reason = "available" if smart is not None else "top_decile_has_fewer_than_20_wallets"
            prior_events = db.execute("SELECT COUNT(DISTINCT event_id) FROM markets WHERE resolved_ts < ?",
                                      (cutoff,)).fetchone()[0]
            cohorts.append({"meeting": meeting, "event_id": event_id, "cutoff_days": days,
                "cutoff_utc": iso(cutoff), "n_qualifying": len(scores), "n_smart": n_smart,
                "smart_status": reason, "n_prior_resolved_meetings": prior_events,
                "minimum_selected_score": min((scores[w]["score"] for w in smart), default=None) if smart else None,
                "placebo_seed": seed})
            for market in sorted((m for m in markets.values() if m.event_id == event_id), key=lambda m:m.market_id):
                quote_ts, p = probability_at(market, cutoff)
                covered = cutoff - 7 * DAY >= floors[event_id]
                row = {"meeting": meeting, "event_id": event_id, "cutoff_days": days,
                    "cutoff_utc": iso(cutoff), "outcome": market.outcome, "market_id": market.market_id,
                    "p_market": p, "probability_utc": iso(quote_ts) if quote_ts is not None else None,
                    "realized": market.realized, "n_smart": n_smart, "n_qualifying": len(scores),
                    "smart_available": smart is not None and covered,
                    "smart_status": reason if covered else "signal_window_outside_api_retention",
                    "window_covered": covered}
                flows = window_flows(db, market.market_id, cutoff)
                for name, members in (("smart", smart), ("placebo", placebo), ("all", None)):
                    result = aggregate_flow(flows, members)
                    if not covered or (name != "all" and members is None):
                        result = dict.fromkeys(result)
                    row.update({f"{name}_{key}": value for key, value in result.items()})
                panel.append(row)
            print(f"{meeting} t-{days}: {len(scores):,} qualifying, {n_smart:,} smart", flush=True)
    return panel, cohorts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path.home() / "data/polymarket")
    parser.add_argument("--probabilities", type=Path, default=ROOT / "datasets/forward_probabilities.csv")
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    data_root = args.data_root.resolve()
    cache = (args.cache or data_root / "wallet_backtest_cache/trades.sqlite3").resolve()
    if cache.is_relative_to(ROOT) or data_root.is_relative_to(ROOT):
        parser.error("Raw data and trade cache must stay outside the repository")
    calendar_path = ROOT / "app/api/calendar_dates.py"
    calendar = runpy.run_path(str(calendar_path))["MEETINGS"]
    markets = load_markets(args.probabilities, data_root / "feasibility/gamma", calendar)
    fingerprint = source_fingerprint(data_root, args.probabilities, calendar_path, markets)
    cache.parent.mkdir(parents=True, exist_ok=True)
    raw_rows, dedup_rows = build_cache(data_root, cache, markets, fingerprint)
    floors = {m.event_id: retention_floor(data_root, m.event_id) for m in markets.values()}
    with sqlite3.connect(cache) as db:
        panel, cohorts = build_panel(db, markets, floors, args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "panel.csv", panel)
    write_csv(args.output_dir / "cohorts.csv", cohorts)
    write_csv(args.output_dir / "settlements.csv", [{"meeting": m.meeting, "event_id": m.event_id,
        "market_id": m.market_id, "outcome": m.outcome, "condition_id": m.condition_id,
        "decision_utc": iso(m.decision_ts), "market_resolution_proxy_utc": iso(m.resolved_ts),
        "meeting_resolution_proxy_utc": iso(max(x.resolved_ts for x in markets.values() if x.event_id == m.event_id)),
        "resolution_basis": m.resolution_basis, "realized": m.realized, "gamma_yes": m.gamma_yes}
        for m in sorted(markets.values(), key=lambda m:(m.decision_ts, m.market_id))])
    write_csv(args.output_dir / "build_manifest.csv", [{"key": key, "value": value} for key, value in {
        "source_fingerprint": fingerprint, "seed": args.seed, "raw_participant_rows": raw_rows,
        "deduplicated_rows": dedup_rows, "duplicate_rows_removed": raw_rows - dedup_rows,
        "panel_rows": len(panel), "minimum_trades": MIN_TRADES, "shrink_trades": SHRINK_TRADES,
        "smart_fraction": SMART_FRACTION, "minimum_smart": MIN_SMART,
        "python_version": platform.python_version()}.items()])
    print(f"Panel: {len(panel)} rows; trades: {raw_rows:,} raw -> {dedup_rows:,} deduplicated")


if __name__ == "__main__":
    main()
