"""Resolution-rule metadata; Gamma endDate is not an observation timestamp."""

from datetime import datetime, timedelta, timezone
import json
import re
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')
MONTHS = 'January February March April May June July August September October November December'.split()


def timestamp(text):
    return int(datetime.fromisoformat(text.replace('Z', '+00:00')).timestamp())


def array(value):
    return json.loads(value) if isinstance(value, str) else value


def title_date(event):
    match = re.search(r'(' + '|'.join(MONTHS) + r') (\d{1,2})(?:,? (20\d\d))?', event['title'])
    if not match:
        raise ValueError('No explicit title date')
    month, day, year = match.groups()
    return datetime(int(year or event['endDate'][:4]), MONTHS.index(month) + 1, int(day), tzinfo=ET)


def rule(event, market, family):
    text = market.get('description', '')
    lower = text.lower()
    symbol = 'BTCUSDT' if family.startswith('btc_') else 'ETHUSDT'
    if 'binance' in lower:
        source = 'Binance/' + symbol
    elif 'chainlink' in lower:
        source = 'Chainlink/' + ('BTCUSD' if family.startswith('btc_') else 'ETHUSD')
    else:
        raise ValueError('Unrecognized resolution source')
    if family.endswith('_weekly'):
        dates = re.findall(r"(\d{1,2}) ([A-Z][a-z]{2}) (?:'\d\d )?(\d{1,2}):(\d\d)", text)
        if len(dates) < 2:
            info = rule(event, market, family.replace('_weekly', '_hourly'))
            return {**info, 'model_compatible': False,
                'exclusion': 'Hourly contract assigned to weekly Gamma series'}
        def endpoint(parts):
            day, month, hour, minute = parts
            return datetime.strptime(f"{event['endDate'][:4]} {month} {day} {hour}:{minute}", '%Y %b %d %H:%M').replace(tzinfo=ET)
        start, end = map(endpoint, dates[:2])
        if not 5 * 86400 < (end-start).total_seconds() < 8 * 86400:
            raise ValueError('Weekly range is not one week')
        strike_ts, expiry = int(start.timestamp()) + 60, int(end.timestamp()) + 60
        cutoff, strike_kind = expiry - (expiry-strike_ts) // 2, 'close'
    elif family.endswith('_hourly'):
        day = title_date(event)
        if not re.search(r'1 hour|1 Hour|1H', text) and not ('Chainlink' in text and 'time range specified in the title' in text):
            raise ValueError('Hourly rule not explicit')
        match = re.search(r'(\d{1,2})(?::(\d\d))?\s*(AM|PM)(?: ET|-)', event['title'], re.I)
        if not match:
            raise ValueError('No explicit hourly title time')
        hour, minute, meridiem = match.groups()
        start = day.replace(hour=int(hour) % 12 + (12 if meridiem.upper() == 'PM' else 0), minute=int(minute or 0))
        strike_ts = int(start.timestamp())
        expiry = strike_ts + 3600
        if market.get('eventStartTime') and timestamp(market['eventStartTime']) != strike_ts:
            raise ValueError('Title and eventStartTime disagree')
        cutoff = expiry - 1800
        strike_kind = 'open'
    else:
        day = title_date(event)
        if not ('12:00' in text or 'noon' in lower or '12PM' in text):
            raise ValueError('Daily noon rule not explicit')
        noon = day.replace(hour=12)
        minute_close = source.startswith('Binance') and 'closing at 12:00' not in text
        expiry = int(noon.timestamp()) + (60 if minute_close else 0)
        cutoff = expiry - 12 * 3600
        strike_ts = int((noon - timedelta(days=1)).timestamp()) + (60 if minute_close else 0)
        strike_kind = 'close'
    threshold = None
    if '_above_' in family:
        match = re.search(r'\$([\d,]+(?:\.\d+)?)([KkMm])?', market['question'])
        if not match:
            raise ValueError('No explicit dollar threshold')
        threshold = float(match[1].replace(',', '')) * {'': 1, 'k': 1000, 'm': 1000000}[str(match[2] or '').lower()]
        strike_ts = None
    return {'symbol': symbol, 'resolution_source': source,
        'resolution_url': market.get('resolutionSource') or ('https://www.binance.com/en/trade/' + symbol.replace('USDT', '_USDT') if source.startswith('Binance') else 'https://data.chain.link/streams'),
        'expiry': expiry, 'cutoff': cutoff, 'strike_ts': strike_ts,
        'strike_kind': strike_kind, 'threshold': threshold,
        'model_compatible': source.startswith('Binance'),
        'exclusion': '' if source.startswith('Binance') else 'Chainlink TWAP is not the free Binance spot resolution series',
        'timing_basis': 'Explicit Gamma resolution description and ET title date/time',
        'utc': datetime.fromtimestamp(expiry, timezone.utc).isoformat()}
