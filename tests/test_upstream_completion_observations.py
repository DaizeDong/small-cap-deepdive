"""Generated source cases distinguish completed observations from missing evidence."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import _deepdive_concepts as concepts
import filter_by_sic as sic
from make_fixtures import (
    downstream_producer_completion_scenarios,
    upstream_completion_scenarios,
)


class Response:
    def __init__(self, payload=None, *, status_code=200, text=""):
        self.payload = payload
        self.status_code = status_code
        self.text = text

    def json(self):
        return deepcopy(self.payload)


@pytest.fixture
def sample():
    return upstream_completion_scenarios()


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setattr(concepts.time, "sleep", lambda *_: None)
    monkeypatch.setattr(concepts, "_sec_tickers_cache", None)


def query(monkeypatch, sample, case, **overrides):
    payload = sample["concept_envelopes"][case]
    monkeypatch.setattr(concepts, "http_get", lambda *_a, **_k: Response(payload))
    return concepts._one_concept(**{**sample["query"], **overrides})


@pytest.mark.parametrize("taxonomy", ["us-gaap", "ifrs-full", "dei"])
def test_query_url_uses_canonical_issuer_identity(monkeypatch, sample, taxonomy):
    query_input = {**sample["query_variants"]["whitespace_cik"], "taxonomy": taxonomy}
    payload = {**sample["concept_envelopes"]["complete_empty"], "taxonomy": taxonomy}
    requested = []

    def fetch(url, **_kwargs):
        requested.append(url)
        return Response(payload)

    monkeypatch.setattr(concepts, "http_get", fetch)
    rows = concepts._one_concept(**query_input)
    canonical_cik = sample["query"]["cik"].zfill(10)
    assert len(requested) == 1
    assert requested[0].endswith(f"/CIK{canonical_cik}/{taxonomy}/{query_input['concept']}.json")
    assert rows.completion["status"] == "complete"
    assert rows.completion["request"]["cik"] == canonical_cik


@pytest.mark.parametrize("case", [
    "complete_empty", "empty_units", "quarterly_only", "future_only",
])
def test_observed_empty_is_complete_after_existing_policy_exclusions(monkeypatch, sample, case):
    rows = query(monkeypatch, sample, case)
    assert rows == []
    assert rows.completion["status"] == "complete"
    assert rows.completion["empty"] is True
    assert rows.completion["row_count"] == 0
    assert rows.completion["requested_work"] == rows.completion["completed_work"] == 1


@pytest.mark.parametrize("case", [
    "nonobject", "mismatched_cik", "mismatched_taxonomy", "mismatched_tag",
    "mismatched_cik_empty", "mismatched_taxonomy_empty", "mismatched_tag_empty",
    "missing_cik", "missing_taxonomy", "missing_tag", "missing_units",
    "units_not_object", "unsupported_nonempty_units", "facts_not_list",
    "nonobject_fact", "bool_val", "string_val", "missing_val", "missing_start",
    "invalid_start", "missing_end", "invalid_end", "missing_filed", "invalid_filed",
])
def test_malformed_evidence_is_never_a_complete_empty_observation(monkeypatch, sample, case):
    rows = query(monkeypatch, sample, case)
    assert rows == []
    assert rows.completion["status"] == "invalid"


def test_valid_rows_survive_malformed_peer_facts_with_invalid_completion(monkeypatch, sample):
    rows = query(monkeypatch, sample, "mixed_malformed")
    assert len(rows) == 1
    assert rows[0]["val"] == sample["concept_envelopes"]["annual"]["units"]["USD"][0]["val"]
    assert rows.completion["status"] == "invalid"
    assert rows.completion["observation"]["malformed_facts"] == 1


@pytest.mark.parametrize("case", ["annual", "mixed", "restatement", "reversed_restatement"])
def test_annual_and_point_in_time_value_selection_is_preserved(monkeypatch, sample, case):
    rows = query(monkeypatch, sample, case)
    facts = sample["concept_envelopes"][case]["units"]["USD"]
    eligible = [fact for fact in facts
                if fact["start"] == sample["concept_envelopes"]["annual"]["units"]["USD"][0]["start"]
                and fact["filed"] <= sample["query"]["asof"]]
    expected = max(eligible, key=lambda fact: fact["filed"])
    assert len(rows) == 1
    assert rows[0]["val"] == expected["val"]
    assert rows[0]["filed"] == expected["filed"]
    assert rows.completion["status"] == "complete"


def test_live_selection_keeps_last_api_fact_order(monkeypatch, sample):
    rows = query(monkeypatch, sample, "reversed_restatement", asof=None)
    assert rows[0]["val"] == sample["concept_envelopes"]["reversed_restatement"]["units"]["USD"][-1]["val"]
    assert rows.completion["status"] == "complete"


def test_registered_instant_balance_does_not_require_start(monkeypatch, sample):
    payload = sample["concept_envelopes"]["instant_assets"]
    rows = query(monkeypatch, sample, "instant_assets", concept=payload["tag"])
    assert rows[0]["val"] == payload["units"]["USD"][0]["val"]
    assert rows.completion["status"] == "complete"


@pytest.mark.parametrize("case", ["rate_limited", "server_error"])
def test_http_failure_keeps_status_without_response_body(monkeypatch, sample, case):
    descriptor = sample["http_cases"][case]
    monkeypatch.setattr(concepts, "http_get", lambda *_a, **_k: Response(**descriptor))
    rows = concepts._one_concept(**sample["query"])
    assert rows == [] and rows.completion["status"] == "unavailable"
    assert rows.completion["observation"]["http_status"] == descriptor["status_code"]
    assert descriptor["text"] not in repr(rows.completion)


def test_request_and_json_failures_have_distinct_completion(monkeypatch, sample):
    def timeout(*_a, **_k):
        raise TimeoutError(sample["http_cases"]["timeout"]["message"])

    monkeypatch.setattr(concepts, "http_get", timeout)
    rows = concepts._one_concept(**sample["query"])
    assert rows.completion["status"] == "unavailable"
    assert rows.completion["work"][0]["reason"] == "request_failed"

    class InvalidJSON(Response):
        def json(self):
            raise ValueError("invalid JSON")

    monkeypatch.setattr(concepts, "http_get", lambda *_a, **_k: InvalidJSON())
    rows = concepts._one_concept(**sample["query"])
    assert rows.completion["status"] == "invalid"
    assert rows.completion["work"][0]["reason"] == "invalid_json"


def test_successful_series_cannot_hide_an_attempted_failed_concept(monkeypatch, sample):
    annual = sample["concept_envelopes"]["annual"]
    assets = sample["concept_envelopes"]["instant_assets"]
    replies = iter([Response(annual), Response(status_code=sample["http_cases"]["rate_limited"]["status_code"])])
    monkeypatch.setattr(concepts, "http_get", lambda *_a, **_k: next(replies))
    rows = concepts.concept_series(sample["query"]["cik"], [annual["tag"], assets["tag"]],
                                   asof=sample["query"]["asof"])
    assert rows[0]["val"] == annual["units"]["USD"][0]["val"]
    assert rows.completion["status"] == "partial"
    assert [item["status"] for item in rows.completion["upstream"]] == ["complete", "unavailable"]


def test_debt_fallback_value_keeps_failed_summand_evidence(monkeypatch, sample):
    annual = sample["concept_envelopes"]["annual"]
    attempted = []

    def fetch(url, **_kwargs):
        tag = url.rsplit("/", 1)[-1].removesuffix(".json")
        attempted.append(tag)
        if tag == concepts.DEBT_SUM_CONCEPTS[1]:
            return Response(status_code=sample["http_cases"]["server_error"]["status_code"])
        payload = deepcopy(annual if tag == concepts.DEBT_SUM_CONCEPTS[0]
                           else sample["concept_envelopes"]["complete_empty"])
        payload["tag"] = tag
        return Response(payload)

    monkeypatch.setattr(concepts, "http_get", fetch)
    rows, label = concepts._debt_series(sample["query"]["cik"], asof=sample["query"]["asof"])
    assert attempted == [*concepts.DEBT_SUM_CONCEPTS, concepts.DEBT_CONCEPT_FALLBACK1,
                         concepts.DEBT_CONCEPT_FALLBACK1B, concepts.DEBT_CONCEPT_FALLBACK1C]
    assert label == concepts.DEBT_SUM_CONCEPTS[0]
    assert rows[0]["components"] == {label: annual["units"]["USD"][0]["val"]}
    assert rows[0]["aggregates"] == {}
    assert concepts.DEBT_SUM_CONCEPTS[1] in rows[0]["missing_components"]
    assert rows[0]["val"] == annual["units"]["USD"][0]["val"]
    assert rows.completion["status"] == "partial"


def test_supplied_plain_ebit_series_remains_unobserved(monkeypatch, sample):
    rows = query(monkeypatch, sample, "annual")
    values, label = concepts._ebit_with_source(sample["query"]["cik"], list(rows))
    assert values == rows and label == concepts.EBIT_PRIMARY_CONCEPT
    assert values.completion["status"] != "complete"


def test_nested_and_later_observation_scopes_do_not_leak(monkeypatch, sample):
    with concepts.concept_observations() as outer:
        query(monkeypatch, sample, "annual")
        with concepts.concept_observations() as inner:
            query(monkeypatch, sample, "complete_empty")
    assert len(outer.completion(1)["upstream"]) == 2
    assert len(inner.completion(0)["upstream"]) == 1
    with concepts.concept_observations() as later:
        pass
    assert later.completion(0)["status"] != "complete"
    assert later.completion(0)["upstream"] == []


def test_ticker_failure_is_retryable_and_cached_success_retains_completion(monkeypatch, sample):
    source = downstream_producer_completion_scenarios()["candidates"][0]
    payload = {"0": {"ticker": source["ticker"], "cik_str": source["cik"], "title": source["name"]}}
    replies = iter([Response(status_code=sample["http_cases"]["server_error"]["status_code"]), Response(payload)])
    monkeypatch.setattr(concepts, "http_get", lambda *_a, **_k: next(replies))
    with concepts.concept_observations() as failed:
        assert concepts._get_sec_tickers() == {}
    assert failed.completion(0)["status"] == "unavailable"
    with concepts.concept_observations() as success:
        value = concepts._get_sec_tickers()
    assert value[source["ticker"]]["cik"] == source["cik"]
    assert success.completion(1)["status"] == "complete"
    with concepts.concept_observations() as cached:
        assert concepts._get_sec_tickers() is value
    assert cached.completion(1)["status"] == "complete"


def enumerate_pages(sample, pages, *, max_pages=None):
    requested = []
    replies = iter(pages)

    def fetch(_url, params, **_kwargs):
        requested.append(params["start"])
        return Response(text=next(replies))

    rows = sic.enumerate_sic(sample["sic"]["code"], count=sample["sic"]["page_size"],
        max_pages=max_pages or sample["sic"]["max_pages"], sleep=0, fetch=fetch)
    return rows, requested


@pytest.mark.parametrize("case, expected", [
    ("explicit_zero", "complete"), ("challenge", "unavailable"),
    ("zero_with_challenge", "unavailable"), ("unrecognized_empty", "unavailable"),
    ("partially_malformed", "invalid"), ("all_malformed", "invalid"),
])
def test_sic_page_diagnostics_distinguish_empty_and_unreadable(sample, case, expected):
    rows, _ = enumerate_pages(sample, [sample["sic"]["html_cases"][case]], max_pages=1)
    assert rows.completion["status"] == expected
    assert rows.completion["pages"][0]["raw_rows"] == sample["sic"]["raw_row_counts"][case]


def test_full_duplicate_sic_page_is_not_a_terminal_short_page(sample):
    rows, requested = enumerate_pages(sample, sample["sic"]["pagination"]["full_duplicates_then_short"])
    assert requested == [0, sample["sic"]["page_size"]]
    assert [row["cik"] for row in rows] == [row["cik"] for row in sample["sic"]["rows"]]
    assert rows.completion["status"] == "complete"


def test_malformed_full_page_retains_rows_and_failure_after_next_page(sample):
    rows, requested = enumerate_pages(sample, sample["sic"]["pagination"]["malformed_then_short"])
    assert len(requested) == 2
    assert [row["cik"] for row in rows] == [row["cik"] for row in sample["sic"]["rows"]]
    assert rows.completion["status"] == "invalid"


def test_repeated_page_and_page_cap_remain_incomplete(sample):
    repeated, _ = enumerate_pages(sample, sample["sic"]["pagination"]["repeated_full_page"])
    assert repeated.completion["status"] == "partial"
    assert any(work["reason"] == "repeated_page" for work in repeated.completion["work"])
    capped, _ = enumerate_pages(sample, [sample["sic"]["html_cases"]["full_duplicates"]], max_pages=1)
    assert capped.completion["status"] == "partial"
    assert any(work["reason"] == "page_cap" for work in capped.completion["work"])
