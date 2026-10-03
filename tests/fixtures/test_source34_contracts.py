"""Generated Source34 controls use actual producers with synthetic I/O."""
from copy import deepcopy
from datetime import date
import io
import json
import math
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

from make_fixtures import source34_scenarios
from test_source33_contracts import _selected

CASE = source34_scenarios()


def _actual_run_sequence(payloads):
    acquisition = CASE["acquisition"]
    queued = deepcopy(payloads)
    requests, share_requests, snapshots, cache_sizes = [], [], [], []
    state = {"rows": []}

    def http_get(url, **kwargs):
        requests.append((url, kwargs))
        payload = queued.pop(0)
        return SimpleNamespace(status_code=200, json=lambda: deepcopy(payload))

    def share_pull(*args, **kwargs):
        share_requests.append((args, kwargs))
        return deepcopy(acquisition["shares"])

    selectors = _selected("tools/_deepdive_concepts.py",
        {"_concept_unit", "_fact_shape_valid", "_annual_entry", "_INSTANT_CONCEPTS", "REVENUE_CONCEPTS"},
        {"date": date, "math": math, "re": re})
    dc = SimpleNamespace(**{k: v for k, v in selectors.items() if k != "__builtins__"})
    dc.http_get = http_get
    row = acquisition["row"]
    panel = {"asof": row["asof"], "theme": "synthetic-acquisition",
             "benchmark": {"total_return": 0.0},
             "names": [{"ticker": row["ticker"], "cik": row["cik"], "total_return": 0.1,
                        "forward_return": {"status": "ok", "entry_price": 12.0}}]}

    def write_features(rows):
        state["rows"] = deepcopy(rows)
        snapshots.append(deepcopy(rows))

    def fake_open(name):
        assert name == "synthetic-panel"
        return io.StringIO(json.dumps(panel))

    class Future:
        def __init__(self, callback, row):
            self.callback, self.row = callback, row

        def result(self):
            return self.callback(self.row)

    class Pool:
        def __init__(self, **kwargs):
            assert kwargs == {"max_workers": 6}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def submit(self, callback, row):
            return Future(callback, row)

    fast = _selected("docs/backtest-2026-06/distress_features_fast.py",
        {"get_facts", "pull_one", "run"},
        {"DC": dc, "date": date, "REVENUE_CONCEPTS": selectors["REVENUE_CONCEPTS"],
         "_shares_series": share_pull,
         "features_path": lambda: SimpleNamespace(exists=lambda: bool(state["rows"])),
         "backtest_files": lambda: ["synthetic-panel"],
         "load_features": lambda: deepcopy(state["rows"]),
         "write_features": write_features, "open": fake_open, "json": json,
         "time": SimpleNamespace(time=lambda: 0.0), "ThreadPoolExecutor": Pool,
         "as_completed": lambda futures: iter(futures),
         "print": lambda *args, **kwargs: None})
    request_counts, share_counts = [], []
    for _ in range(3):
        fast["run"]()
        request_counts.append(len(requests))
        share_counts.append(len(share_requests))
        cache_sizes.append(len(fast["_cache"]))
    assert fast["get_facts"](row["cik"]) == acquisition["good"]["facts"]["us-gaap"]
    assert len(requests) == request_counts[-1]
    return snapshots, request_counts, share_counts, cache_sizes, queued


@pytest.mark.parametrize("case", CASE["acquisition"]["malformed"], ids=lambda case: case["name"])
def test_same_module_actual_run_recovers_after_nested_or_unusable_facts(case):
    before = deepcopy(case)
    rows, calls, shares, cache, queued = _actual_run_sequence(
        [case["payload"], CASE["acquisition"]["good"]])
    assert case == before
    first, second, third = (batch[0] for batch in rows)
    assert first["acquisition_status"] == "partial"
    assert first["series"]["shares"] == CASE["acquisition"]["shares"]
    assert not any(points for key, points in first["series"].items() if key != "shares")
    assert second["acquisition_status"] == "complete" and "pull_error" not in second
    assert second["series"]["cash"][0]["val"] == 30
    assert second["series"]["shares"] == CASE["acquisition"]["shares"]
    assert third == second
    assert calls == [1, 2, 2] and shares == [1, 2, 2]
    assert cache == [0, 1, 1] and queued == []


def test_successful_cache_and_complete_resume_remain_effective():
    rows, calls, shares, cache, queued = _actual_run_sequence([CASE["acquisition"]["good"]])
    assert all(batch[0]["acquisition_status"] == "complete" for batch in rows)
    assert rows[0] == rows[1] == rows[2]
    assert calls == [1, 1, 1] and shares == [1, 1, 1]
    assert cache == [1, 1, 1] and queued == []


@pytest.mark.parametrize("name,checked,mismatch,field", [
    ("debt_mismatch", True, True, "total_debt"),
    ("agreement", True, False, None),
    ("unavailable", False, False, None),
    ("revenue_mismatch", True, True, "revenue"),
    ("floor", True, False, None),
])
def test_generated_independent_source_inputs_preserve_comparator_branches(name, checked, mismatch, field):
    core = _selected("tools/deepdive_data.py", {"_cross_source_check"}, {"math": math})
    actual = core["_cross_source_check"](*deepcopy(CASE["cross_source"][name]))
    assert actual[0] is checked and actual[1] is mismatch
    if field is not None:
        assert field in actual[2] and "ratio" in actual[2]
