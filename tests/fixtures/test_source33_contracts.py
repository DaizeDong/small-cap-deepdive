"""Generated acquisition/retry controls; all provider callbacks are synthetic."""
import ast
from copy import deepcopy
from datetime import date
import math
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

from make_fixtures import source33_scenarios
from test_source32_contracts import _resume_runner

ROOT = Path(__file__).resolve().parents[2]
CASE = source33_scenarios()


def _selected(path, names, supplied):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    available = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            available[node.name] = node
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                if isinstance(target, ast.Name):
                    available[target.id] = node
    wanted, queue = set(names), list(names)
    while queue:
        for node in ast.walk(available[queue.pop()]):
            if (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
                    and node.id in available and node.id not in wanted and node.id not in supplied):
                wanted.add(node.id)
                queue.append(node.id)
    picked = [node for node in tree.body if any(node is available[name] for name in wanted)]
    assert all(not getattr(node, "decorator_list", []) for node in picked)
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    namespace = dict(supplied)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[future, *picked], type_ignores=[])),
                 "<selected-production-functions>", "exec"), namespace)
    return namespace


def _producer(events, shares):
    requests, share_requests = [], []
    events, shares = deepcopy(events), list(shares)

    def http_get(url, **kwargs):
        requests.append((url, kwargs))
        event = events.pop(0)
        if event == "timeout":
            raise TimeoutError("synthetic transport timeout")

        def payload():
            if event == "invalid_json":
                raise ValueError("synthetic JSON failure")
            if event == "invalid_shape":
                return {"facts": {"us-gaap": ["invalid"]}}
            if event == "empty":
                return {"facts": {"us-gaap": {}}}
            return deepcopy(CASE["companyfacts"])

        return SimpleNamespace(status_code=503 if event == "http_503" else 200, json=payload)

    def share_pull(*args, **kwargs):
        share_requests.append((args, kwargs))
        event = shares.pop(0)
        if event == "timeout":
            raise TimeoutError("synthetic shares timeout")
        return [] if event == "empty" else deepcopy(CASE["shares"])

    selectors = _selected("tools/_deepdive_concepts.py",
                          {"_concept_unit", "_fact_shape_valid", "_annual_entry",
                           "_INSTANT_CONCEPTS", "REVENUE_CONCEPTS"},
                          {"date": date, "math": math, "re": re})
    dc = SimpleNamespace(**{key: value for key, value in selectors.items() if key != "__builtins__"})
    dc.http_get = http_get
    fast = _selected("docs/backtest-2026-06/distress_features_fast.py", {"get_facts", "pull_one"},
                     {"DC": dc, "date": date, "REVENUE_CONCEPTS": selectors["REVENUE_CONCEPTS"],
                      "_shares_series": share_pull})
    return fast, requests, share_requests


@pytest.mark.parametrize("event", CASE["failed_companyfacts"])
def test_actual_producer_failure_remains_retryable_and_is_not_negatively_cached(event):
    fast, requests, share_requests = _producer([event, "ok"], ["timeout", "ok"])
    row = deepcopy(CASE["row"])
    first = fast["pull_one"](row)
    assert row == CASE["row"]
    assert len(first["series"]) == 13 and all(points == [] for points in first["series"].values())
    assert first["acquisition_status"] == "unavailable"
    assert fast["_cache"] == {}
    snapshots, attempted = _resume_runner({"prior": [first], "tickers": ["SYNACQUIRE"],
                                          "failures": [], "checkpoint": False})
    assert attempted == ["SYNACQUIRE"] and len(snapshots[-1]) == 1
    recovered = fast["pull_one"](first)
    assert recovered["acquisition_status"] == "complete" and "pull_error" not in recovered
    assert recovered["series"]["cash"][0]["val"] == 30
    assert recovered["series"]["shares"] == CASE["shares"]
    assert first["acquisition_status"] == "unavailable"
    assert len(requests) == 2 and len(share_requests) == 2
    assert len(fast["_cache"]) == 1


@pytest.mark.parametrize("channel", ["companyfacts", "shares"])
def test_partial_acquisition_is_retained_and_retry_recovers(channel):
    fast, requests, share_requests = _producer(["http_503", "ok"] if channel == "companyfacts" else ["ok"],
                                              ["ok", "ok"] if channel == "companyfacts" else ["timeout", "ok"])
    first = fast["pull_one"](CASE["row"])
    assert first["acquisition_status"] == "partial" and any(first["series"].values())
    snapshots, attempted = _resume_runner({"prior": [first], "tickers": [],
                                          "failures": [], "checkpoint": False})
    assert attempted == [] and snapshots[-1] == [first]
    snapshots, attempted = _resume_runner({"prior": [first], "tickers": ["SYNACQUIRE"],
                                          "failures": ["SYNACQUIRE"], "checkpoint": False})
    assert attempted == ["SYNACQUIRE"]
    assert snapshots[-1][0]["acquisition_status"] == "unavailable"
    recovered = fast["pull_one"](first)
    assert recovered["acquisition_status"] == "complete" and "pull_error" not in recovered
    assert len(requests) == (2 if channel == "companyfacts" else 1)
    assert len(share_requests) == 2


@pytest.mark.parametrize("case", CASE["resume_statuses"], ids=lambda case: case["name"])
def test_resume_uses_evidence_and_explicit_status(case):
    row = deepcopy(CASE["row"])
    row["series"] = ({name: [] for name in CASE["series_names"]} if case["empty"]
                     else {"cash": [{"end": "1999-12-31", "val": 30}]})
    if case["status"] is not None:
        row["acquisition_status"] = case["status"]
    if case["error"]:
        row["pull_error"] = "synthetic acquisition failure"
    snapshots, attempted = _resume_runner({"prior": [row], "tickers": ["SYNACQUIRE"],
                                          "failures": [], "checkpoint": False})
    assert attempted == (["SYNACQUIRE"] if case["retry"] else [])
    assert len(snapshots[-1]) == 1
    if not case["retry"]:
        assert snapshots[-1] == [row]
