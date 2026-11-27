# Round-seven options-to-event search

Do VIX or the VIX9D/VIX term structure predict archived FOMC, CPI, payroll and
unemployment probabilities? This mirrors round six's exact event population,
split and statistical methods. The approved differences are official CBOE
option-index predictors, 16:15/13:15 ET boundaries, and fixed 1% log-change units.
MOVE is excluded before performance. See PREREGISTRATION.md and registration.json.

From the repository root with the provisioned environment:

```sh
PYTHON=/home/ubuntu/data/polymarket/wallet_backtest_env/bin/python
$PYTHON models/options_to_event_search/archive.py
$PYTHON models/options_to_event_search/register_study.py feasibility
$PYTHON -m unittest discover -s models/options_to_event_search -p 'test_*.py' -v
$PYTHON models/options_to_event_search/register_study.py preregister
# Commit and push preregistration before proceeding.
$PYTHON models/options_to_event_search/study.py development
# Commit the development freeze before proceeding.
$PYTHON models/options_to_event_search/study.py holdout
```

The collector creates its archive directory before writing. Raw public responses,
the constructed panel, development copy and exclusive retained holdout lock live
in `~/data/polymarket/options_to_event_search/`, outside Git. Existing FOMC/macro
databases are opened read-only. No crypto/ETH or forward-test data is used.
Never delete or reset a freeze or lock to repeat a search. Unit fixtures are
synthetic, network-disabled and use temporary state; a fixture's printed holdout
message is not the study result.
