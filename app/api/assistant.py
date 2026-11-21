import re
from calendar import month_abbr, month_name
from datetime import date
from typing import Literal

from data import WATCHLIST
from forecast import forecast
from schemas import Answer, AssistantRequest

SourceFile = Literal["forward_probabilities.csv", "index_daily.csv", "daily_cluster_signals.csv"]
MARKETS = "datasets/forward_probabilities.csv"
PRICES = "datasets/index_daily.csv"
WALLET_SIGNALS = "datasets/polymarket/wallet_cluster_pilot/fed_20260531_v1/daily_cluster_signals.csv"
CALENDAR = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
MONTHS = "|".join(name.lower() for name in [*month_name[1:], *month_abbr[1:], "Sept"])
MONTH_NUMBER = {name.lower(): i for i, name in enumerate(month_abbr) if i}
DATE = re.compile(rf"\b(?:(?P<iso>\d{{4}}-\d{{2}}-\d{{2}})|(?P<month>{MONTHS})\.?\s+(?P<day>\d{{1,2}})(?:st|nd|rd|th)?(?:(?:,\s*|\s+)(?P<year>\d{{4}}))?)\b")
MEETING = re.compile(rf"\b(?P<month>{MONTHS})(?:\s+(?P<year>\d{{4}}))?\s+(?:fomc\b|(?:fed\s+)?(?:meeting|rate decision)\b)")
MEETING_IN = re.compile(rf"\b(?:fomc|meeting|rate decision) (?:in|for) (?P<month>{MONTHS})(?:\s+(?P<year>\d{{4}}))?\b")
MONTH_REFERENCE = re.compile(rf"\b(?:in|for|at) (?:the )?(?:{MONTHS})(?: \d{{4}})?\b")
HORIZONS = {"1": 1, "one": 1, "5": 5, "five": 5, "20": 20, "twenty": 20}
NUMBER_WORD = (
    r"(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|"
    r"fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|"
    r"ninety|hundred|thousand|half)"
)
HORIZON = re.compile(rf"(?<!\w)([+-]?(?:\d+(?:\.\d+)?|\.\d+)|{NUMBER_WORD}(?:[ -]+{NUMBER_WORD})*)"
                     r"[ -]*(?:trading[ -]+)?(?:days?|d)\b")
OTHER_DATE = re.compile(r"\b(?:yesterday|tomorrow|last (?:week|month|year)|\d{1,2}/\d{1,2})\b")
ODDS = re.compile(r"\b(?:probabilit(?:y|ies)|odds|chance(?:s)?|likelihood|how likely)\b")
FORECAST = re.compile(r"\b(?:forecast(?:s)?|volatility|qlike|mse)\b")
RISK = re.compile(r"\b(?:var|es|expected shortfall|value[- ]at[- ]risk)\b")
SOURCES = re.compile(r"\b(?:sources?|citations?|verify|evidence|where .* (?:come|from))\b")
CUT = r"\b(?:cuts?|cutting|lower(?:s|ed|ing)?|decreas(?:e[ds]?|ing)|reduc(?:e[ds]?|ing))\b"
HIKE = r"\b(?:hikes?|hiking|rais(?:e[ds]?|ing)|increas(?:e[ds]?|ing))\b"
UNCHANGED = r"\b(?:no change|unchanged|hold(?:s|ing)? (?:interest )?rates?|held (?:interest )?rates?|rates? (?:stay(?:s|ed)?|remain(?:s|ed)?) (?:the same|steady))\b"
BPS = re.compile(r"\b(\d+)\s*(\+)?\s*[- ]?\s*(?:bps?|basis points?)\b")
COMPARISON = re.compile(r"\b(?:compare[ds]?|comparison|versus|vs\.?|rather than)\b")
COMPANY_TICKERS = {"apple": "AAPL", "microsoft": "MSFT", "nvidia": "NVDA", "amazon": "AMZN", "tesla": "TSLA"}
FALLBACK = ("I couldn’t match that to the research data. Ask a standalone question about Fed market odds, "
            "the meeting decision, or the SPY volatility forecast. I don’t browse the web or remember earlier questions.")


def observed_on(text, year):
    match = DATE.search(text)
    if not match:
        return None
    if match["iso"]:
        return date.fromisoformat(match["iso"]).isoformat()
    return date(int(match["year"] or year), MONTH_NUMBER[match["month"][:3]], int(match["day"])).isoformat()


def outcome_filter(text):
    if re.search(UNCHANGED, text):
        return "No change", lambda outcome: outcome == "No change"
    cut, hike = re.search(CUT, text), re.search(HIKE, text)
    if bool(cut) == bool(hike):
        return None, None
    direction = "decrease" if cut else "increase"
    size = BPS.search(text)
    amount = f"{size[1]}{size[2] or ''} bps" if size else next(
        (bps for phrasing, bps in ((r"quarter[ -](?:percentage[ -])?point", "25 bps"),
                                  (r"half[ -](?:percentage[ -])?point", "50 bps")) if re.search(phrasing, text)), None)
    if amount:
        label = f"{amount} {direction}"
        return label, lambda outcome: outcome == label
    return f"rate {'cut' if cut else 'hike'}", lambda outcome: outcome.endswith(f" {direction}")


def market_answer(text, request, event, run):
    if any(re.search(rf"\b{asset}\b", text) for asset in (*map(str.lower, WATCHLIST), *COMPANY_TICKERS)):
        return "The market-probability data covers Fed rate decisions, not individual asset prices.", ()
    dates = list(DATE.finditer(text))
    directions = sum(bool(re.search(pattern, text)) for pattern in (CUT, HIKE, UNCHANGED))
    if COMPARISON.search(text) or len(dates) > 1 or directions > 1 or len(BPS.findall(text)) > 1:
        return "Ask separately for each rate outcome or observation date so I can look up both without mixing them.", ()
    if not dates and MONTH_REFERENCE.search(text) and not (MEETING.search(text) or MEETING_IN.search(text)):
        return ("For market odds on a past day, include the exact observation date. "
                "To ask about a different Fed meeting, select it first."), ()
    label, matches = outcome_filter(text)
    selected = re.search(r"\b(?:this|the selected|the chosen) (?:market )?outcome\b", text)
    all_outcomes = re.search(r"\b(?:all|each|every) (?:market |possible )?outcomes?\b|\bprobabilities\b", text)
    if not (matches or selected) and re.search(
        r"\b(?:probabilit(?:y|ies)|odds|chances?|likelihood) (?:for|of|that) "
        r"(?!this (?:meeting|event)\b|the (?:selected )?(?:fed )?meeting\b|all (?:market )?outcomes\b)",
        text,
    ):
        return FALLBACK, ()
    odds = ODDS.search(text)
    if odds and not (matches or selected or all_outcomes or DATE.search(text) or OTHER_DATE.search(text)):
        tail = text[odds.end():].strip(" ?.!")
        if tail not in ("", "now", "today", "currently", "did this run use") and not re.search(
            r"\b(?:this (?:meeting|event)|the (?:selected )?(?:fed )?meeting)\b", tail
        ):
            return FALLBACK, ()
    if not event:
        return "Select a Fed meeting to look up its market probabilities.", ()

    name = event["title"]
    evidence = (f"event:{event['id']}", MARKETS)
    try:
        day = observed_on(text, event["meeting_date"][:4])
    except ValueError:
        return "That date isn’t valid. Try a date such as 2026-09-01.", ()
    if not day and OTHER_DATE.search(text):
        return "Give an exact observation date (for example 2026-09-01) to look up historical market odds.", ()

    if not matches and not all_outcomes:
        label = run["request"]["outcome"] if run else request.outcome
        if label:
            matches = lambda outcome: outcome == label
    if run and not day and label == run["request"]["outcome"]:
        saved = run["results"]
        return (f"{name} · {label}: this run used {saved['probability']:.2%}, observed on "
                f"{saved['probability_date']} (run cutoff {saved['as_of']}). This is a historical market price.",
                (f"run:{run['id']}",))

    if day:
        snapshots = [{"outcome": outcome, **row}
                     for outcome, history in event["history"].items() for row in history if row["date"] == day]
    else:
        snapshots = event["latest_snapshot"]
    if matches:
        snapshots = [row for row in snapshots if matches(row["outcome"])]
    if not snapshots:
        when = f" on {day}" if day else ""
        return f"{name}: no market observation for {label or 'these outcomes'}{when} in the available data.", evidence

    window = f"observations on {day}" if day else "latest dataset observations"
    if run:
        window += f" through the run cutoff ({run['results']['as_of']})"
    values = "; ".join(f"{row['outcome']}: {row['market_probability']:.2%} (observed {row['date']})" for row in snapshots)
    return f"{name} · {window}: {values}. These are historical market prices, not live odds.", evidence


def forecast_answer(text, request, run):
    names = {asset.lower(): asset for asset in WATCHLIST if asset != "SPY"} | COMPANY_TICKERS
    unsupported = list(dict.fromkeys(ticker for name, ticker in names.items() if re.search(rf"\b{name}\b", text)))
    if unsupported:
        return f"No volatility forecast is available for {', '.join(unsupported)}. Only SPY has price data here.", ()
    if DATE.search(text) or OTHER_DATE.search(text) or re.search(r"\bhistorical\b", text):
        return "I can show the latest dataset forecast, but can’t look up a forecast for a requested date.", ()
    run_forecast = re.search(r"\b(?:this run|portfolio|scenario)\b", text) is not None
    if run_forecast and not run:
        return "Open a saved run to ask about its portfolio volatility.", ()
    run_subjects = {"run", "portfolio", "scenario"} if run_forecast else set()
    subject = re.search(r"\b(?:forecast|volatility) (?:for|of|on) (?:the )?([a-z]+)\b", text)
    owner = re.search(r"\b([a-z]+)'s (?:volatility )?forecast\b", text)
    if ((subject and subject[1] not in {"spy", "this", "selected", "next", "that", *run_subjects}
         and not HORIZON.match(text, subject.start(1)))
            or (owner and owner[1] not in {"spy", "model", "eventlens", *run_subjects})):
        return "I can only show the SPY volatility forecast. Name SPY and a supported horizon (1, 5 or 20 trading days).", ()

    horizons = {HORIZONS.get(value) for value in HORIZON.findall(text)}
    if (len(horizons) > 1 or None in horizons
            or re.search(r"\b(?:next|one|two|a|\d+) (?:weeks?|months?|years?)\b", text)):
        return "Choose one supported forecast horizon: 1, 5 or 20 trading days.", ()
    if run_forecast:
        horizon = run["request"]["horizon"]
        if horizons and horizon not in horizons:
            return f"This run used {horizon} trading days. Run a new scenario to change its horizon.", (f"run:{run['id']}",)
        results = run["results"]
        return (f"This saved run estimates {results['horizon_volatility']:.3%} portfolio volatility over "
                f"{horizon} trading days, not annualized (run cutoff {results['as_of']}).",
                (f"run:{run['id']}",))
    horizon = next(iter(horizons), request.horizon or (run["request"]["horizon"] if run else 5))
    result = forecast(horizon)
    comparison = "; ".join(
        f"{name} {m['latest_volatility']:.3%} (out-of-sample MSE {m['mse']:.6g}, QLIKE {m['qlike']:.4f}, n={m['n']})"
        for name, m in result["models"].items()
    )
    context = " This is the latest model output, not a reconstruction of the saved run." if run else ""
    return (f"SPY {horizon}-trading-day volatility forecast as of {result['as_of']} (not annualized): "
            f"{comparison}. Lower MSE and QLIKE are better on the same test dates.{context}", (PRICES, MARKETS))


def wallet_answer(event, run):
    sources = [MARKETS]
    if event:
        sources.append(f"event:{event['id']}")
    if run:
        sources.append(f"run:{run['id']}")
    if event and event["wallet_informed"]["available"]:
        wallet = event["wallet_informed"]
        market = {row["outcome"]: row["market_probability"] for row in event["latest_snapshot"]}
        answer = f"Wallet-informed estimate: {wallet['method']}. Signal date: {wallet['signal_timestamp']}. "
        answer += "; ".join(
            f"{row['outcome']}: wallet {row['wallet_probability']:.4%} versus market {market[row['outcome']]:.4%} "
            f"({(row['wallet_probability'] - market[row['outcome']]) * 100:+.4f} percentage points)"
            for row in wallet["outcomes"]
        )
        answer += (". Active-wallet-weighted directional imbalance tilts each market logit by k=0.5, then "
                   "probabilities are normalized across outcomes; missing imbalance gives zero tilt. "
                   "This is not calibrated or validated predictive evidence.")
        sources.append(WALLET_SIGNALS)
    else:
        reason = event["wallet_informed"]["reason"] if event else "Supply an event_id or run_id to inspect wallet coverage"
        answer = f"Wallet-informed estimates are unavailable: {reason}."
    answer += " Market probabilities are raw traded prices. Wallet estimates are not used in forecasts or scenarios."
    if run:
        answer += " Run assumptions: " + " ".join(run["results"]["assumptions"])
    return answer, tuple(sources)


def answer_topic(text, request, event, run):
    if event and (meeting := MEETING.search(text) or MEETING_IN.search(text)):
        month = MONTH_NUMBER[meeting["month"][:3]]
        year = meeting["year"] or event["meeting_date"][:4]
        if event["meeting_month"] != f"{year}-{month:02}":
            return f"You’re viewing {event['title']}. Select the meeting you meant before asking about it.", ()

    if re.search(r"\b(?:weather|rain|gold|bitcoin|crypto|earnings|inflation|temperature)\b", text):
        return FALLBACK, ()
    if re.search(r"\b(?:wallets?|wallet-informed|smart money)\b", text):
        return wallet_answer(event, run)
    if re.search(r"\b(?:why (?:do|are) (?:the )?estimates differ|baseline (?:vs\.?|versus|and) (?:the )?augmented|why .*forecasts? differ|difference between (?:the )?(?:baseline|models))\b", text):
        answer = ("The baseline model uses past SPY returns. The augmented model also uses the next meeting’s "
                  "No change market probability and its five-day change. More inputs don’t guarantee a better forecast.")
        if event and re.search(r"\bestimates differ\b", text):
            wallet_text, sources = wallet_answer(event, run)
            return answer + "\n\n" + wallet_text, (PRICES, MARKETS, *sources)
        return answer, (PRICES, MARKETS)
    if event and text.startswith("why ") and ODDS.search(text) and re.search(r"\b(?:resolved|100\s*%|settled)\b", text):
        return (f"{event['title']}: a market observation is a historical traded price, not the final outcome. "
                "A price before settlement doesn’t have to be 0% or 100%, even when the decision is known today.",
                (f"event:{event['id']}", MARKETS))
    if RISK.search(text):
        answer = ("95% VaR is the loss threshold exceeded in about 5% of simulations, not a maximum loss. "
                  "Expected shortfall (ES) averages the worst 5% of losses.")
        sources = ()
        if run:
            results = run["results"]
            answer += f" This run: VaR {results['var_95_pct']:.3f}%, ES {results['es_95_pct']:.3f}%."
            sources = (f"run:{run['id']}",)
        else:
            answer += " Open a saved run to ask for its values."
        if FORECAST.search(text):
            forecast_text, forecast_sources = forecast_answer(text, request, run)
            return forecast_text + "\n\n" + answer, forecast_sources + sources
        return answer, sources
    if FORECAST.search(text):
        if ODDS.search(text) and not re.search(r"\b(?:input|uses?|feature|affect)\b", text):
            return "Ask for the Fed market odds and the SPY forecast as separate questions, or spell out both questions.", ()
        return forecast_answer(text, request, run)
    if ODDS.search(text) or re.search(r"^(?:and )?what about\b", text) and outcome_filter(text)[1]:
        return market_answer(text, request, event, run)
    if event and re.search(r"\b(?:volume|how much (?:was|has been) traded)\b", text):
        prefix = "Daily trading volume is unavailable. " if DATE.search(text) or OTHER_DATE.search(text) else ""
        return (f"{prefix}{event['title']}: ${event['total_volume']:,.0f} traded across its markets over their lifetime, "
                "not on a particular date.", (f"event:{event['id']}", MARKETS))
    if event and not text.startswith("why ") and re.search(
        r"\b(?:actual(?:ly)? decide|decision date|realized (?:outcome|decision)|(?:is|was) it (?:resolved|settled)|"
        r"what (?:did the (?:fed|fomc) (?:decide|do)|happened(?: at| in)?|was the (?:actual )?(?:decision|outcome))|"
        r"when (?:was|is) (?:the|this) meeting)\b", text
    ):
        result = f"Recorded outcome: {event['realized_outcome']}." if event["realized_outcome"] else "No realized outcome is available in this view."
        return (f"{event['title']}: decision date {event['meeting_date']} ({event['status']}). {result}",
                (f"event:{event['id']}", MARKETS, CALENDAR))
    if SOURCES.search(text):
        if run:
            return "The saved run records its inputs, results and dataset version. Follow the run link to verify them.", (f"run:{run['id']}",)
        if event:
            return (f"To verify market observations for {event['title']}, open its event details or filter the market "
                    f"CSV by event_id {event['id']}, outcome and observation date. Decision dates come from the FOMC calendar.",
                    (f"event:{event['id']}", MARKETS, CALENDAR))
    return FALLBACK, ()


def answer_question(request: AssistantRequest, event: dict | None, run: dict | None) -> Answer:
    text = request.question.lower().replace("’", "'").replace("–", "-")
    parts = re.split(r"\?[\s]+|[,;]?\s+and\s+(?=(?:what|where|when|how|is|can|show|give)\b)", text)
    answers, citations = [], []
    for part in parts:
        answer, sources = answer_topic(part.strip(), request, event, run)
        if answer not in answers:
            answers.append(answer)
        citations.extend(sources)
    return Answer(answer="\n\n".join(answers), citations=list(dict.fromkeys(citations)))
