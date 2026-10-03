"""Generated Source32 resume regressions with synthetic in-memory dependencies."""
import ast
from copy import deepcopy
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from make_fixtures import source32_scenarios

CASE = source32_scenarios()
ROOT = Path(__file__).resolve().parents[2]


def _resume_runner(case):
    source = (ROOT / "docs/backtest-2026-06/distress_features_fast.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    run, = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "run"]
    assert not run.decorator_list
    prior = deepcopy(case["prior"])
    before = deepcopy(prior)
    snapshots, attempted = [], []
    panel = {"asof": "2000-01-01", "theme": "synthetic-theme",
             "benchmark": {"total_return": 0.0},
             "names": [{"ticker": ticker, "cik": "42", "total_return": 0.1,
                        "forward_return": {"status": "ok", "entry_price": 10.0}}
                       for ticker in case["tickers"]]}

    def fake_open(name):
        assert name == "synthetic-panel"
        return io.StringIO(json.dumps(panel))

    def pull(row):
        attempted.append(row["ticker"])
        if row["ticker"] in case["failures"]:
            raise RuntimeError("synthetic retry failure")
        result = deepcopy(row)
        result["series"] = {"cash": [{"end": "1999-12-31", "val": 20}]}
        return result

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
            assert callback is pull
            return Future(callback, row)

    namespace = {
        "features_path": lambda: SimpleNamespace(exists=lambda: bool(prior)),
        "backtest_files": lambda: ["synthetic-panel"] if case["tickers"] else [],
        "load_features": lambda: deepcopy(prior),
        "write_features": lambda rows: snapshots.append(deepcopy(rows)),
        "time": SimpleNamespace(time=lambda: 0.0),
        "ThreadPoolExecutor": Pool,
        "as_completed": lambda futures: iter(futures),
        "pull_one": pull,
        "open": fake_open,
        "json": json,
        "print": lambda *args, **kwargs: None,
    }
    exec(compile(ast.Module(body=[run], type_ignores=[]), "<shipped-fast-run>", "exec"), namespace)
    namespace["run"]()
    assert prior == before
    return snapshots, attempted


@pytest.mark.parametrize("case", CASE["resume"], ids=lambda case: case["name"])
def test_fast_resume_preserves_observations_and_replaces_retries(case):
    snapshots, attempted = _resume_runner(case)
    prior = {row["ticker"]: row for row in case["prior"]}
    successful = {ticker for ticker, row in prior.items() if row.get("series")}
    expected_attempts = [ticker for ticker in case["tickers"] if ticker not in successful]
    assert attempted == expected_attempts
    assert len(snapshots) == (2 if case["checkpoint"] else 1)
    final = snapshots[-1]
    keys = [(row["ticker"], row["asof"]) for row in final]
    assert len(keys) == len(set(keys)) == len(set(prior) | set(case["tickers"]))
    final_by_ticker = {row["ticker"]: row for row in final}
    for ticker, old in prior.items():
        if ticker not in expected_attempts:
            assert final_by_ticker[ticker] == old
    for ticker in expected_attempts:
        row = final_by_ticker[ticker]
        assert "synthetic_marker" not in row
        if ticker in case["failures"]:
            assert row["series"] == {}
            assert row["pull_error"] == "synthetic retry failure"
        else:
            assert row["series"] == {"cash": [{"end": "1999-12-31", "val": 20}]}
            assert "pull_error" not in row
    if case["checkpoint"]:
        checkpoint = {row["ticker"]: row for row in snapshots[0]}
        assert len(checkpoint) == 41
        assert checkpoint["SYNFAILED"] == prior["SYNFAILED"]
        assert final_by_ticker["SYNFAILED"]["series"] != prior["SYNFAILED"]["series"]
