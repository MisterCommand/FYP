import pytest

from analysis import analyze, outcome_matches
from data import event_rows
from schemas import AnalysisRequest


@pytest.mark.parametrize("outcome,realized,expected", [
    ("25+ bps increase", "25 bps increase", True),
    ("25+ bps increase", "50+ bps increase", True),
    ("50+ bps decrease", "50 bps decrease", True),
    ("50+ bps decrease", "75+ bps decrease", True),
    ("50+ bps decrease", "25 bps decrease", False),
    ("25+ bps increase", "25 bps decrease", False),
    ("25+ bps increase", "No change", False),
    ("25 bps increase", "50 bps increase", False),
    ("No change", "no change", True),
    ("No change", "25 bps increase", False),
    ("25 bps increase", "25+ bps increase", None),
    ("50+ bps increase", "25+ bps increase", None),
    ("", "25 bps increase", None),
    ("25+ bps increase", "unknown", None),
])
def test_semantic_outcome_matches(outcome, realized, expected):
    assert outcome_matches(outcome, realized) is expected


def test_inclusive_increase_uses_historical_quarter_point_increases():
    request = AnalysisRequest(event_id="903377", outcome="25+ bps increase",
                              holdings=[{"asset": "SPY", "weight": 1}], horizon=5)
    result = analyze(request, event_rows(request.event_id))
    assert result["sample_counts"] == {"yes": 5, "no": 21}
    assert result["ambiguous_outcome_samples"] == 0
    assert result["conditional_spy"]["yes"]["status"] == "Historical"
