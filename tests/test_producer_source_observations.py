"""Source observation failures survive producer persistence and receipt reconstruction."""
from copy import deepcopy
import json

import pytest

from test_deepdive_producer_completion import producer, runtime, sample, stages, survivors
from make_fixtures import upstream_completion_scenarios


class Response:
    def __init__(self, payload=None, *, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return deepcopy(self.payload)


@pytest.fixture
def upstream():
    return upstream_completion_scenarios()


@pytest.mark.parametrize("case, status", [
    ("valid", "complete"), ("explicit_empty", "complete"),
    ("missing_sic", "invalid"), ("mismatched_cik", "invalid"),
    ("malformed_sic", "invalid"), ("nonobject", "invalid"),
])
def test_submissions_scope_and_explicit_absence(monkeypatch, upstream, case, status):
    requested = []

    def fetch(url, **_kwargs):
        requested.append(url)
        return Response(upstream["submissions"][case])

    monkeypatch.setattr(producer, "http_get", fetch)
    code, completion = producer._sic_observation(upstream["query_variants"]["whitespace_cik"]["cik"])
    assert completion["status"] == status
    assert completion["request"]["cik"] == upstream["query"]["cik"].zfill(10)
    assert requested == [
        f"https://data.sec.gov/submissions/CIK{upstream['query']['cik'].zfill(10)}.json"]
    if status == "complete":
        assert code == upstream["submissions"][case]["sic"]
        assert completion["empty"] is (code == "")
    else:
        assert code is None


@pytest.mark.parametrize("case", ["rate_limited", "server_error"])
def test_submissions_http_failure_remains_unavailable(monkeypatch, upstream, case):
    status = upstream["http_cases"][case]["status_code"]
    monkeypatch.setattr(producer, "http_get", lambda *_a, **_k: Response(status_code=status))
    code, completion = producer._sic_observation(upstream["query"]["cik"])
    assert code is None
    assert completion["status"] == "unavailable"
    assert completion["observation"]["http_status"] == status


def test_submissions_transport_and_json_failures_remain_distinct(monkeypatch, upstream):
    def timeout(*_args, **_kwargs):
        raise TimeoutError(upstream["http_cases"]["timeout"]["message"])

    monkeypatch.setattr(producer, "http_get", timeout)
    _, completion = producer._sic_observation(upstream["query"]["cik"])
    assert completion["status"] == "unavailable"
    assert completion["work"][0]["reason"] == "request_failed"

    class InvalidJSON(Response):
        def json(self):
            raise ValueError("Synthetic invalid JSON")

    monkeypatch.setattr(producer, "http_get", lambda *_a, **_k: InvalidJSON())
    _, completion = producer._sic_observation(upstream["query"]["cik"])
    assert completion["status"] == "invalid"
    assert completion["work"][0]["reason"] == "invalid_json"


@pytest.mark.parametrize("case, expected", [
    ("annual", "complete"), ("complete_empty", "complete"),
    ("mixed_malformed", "invalid"), ("http_failure", "partial"),
])
def test_observations_survive_persistence_and_receipt_reconstruction(
        monkeypatch, runtime, sample, upstream, case, expected):
    path = survivors(runtime, sample)

    def pull(ticker, cik):
        selected = case if ticker == sample["survivor_rows"][0]["ticker"] else "annual"
        payload = deepcopy(upstream["concept_envelopes"][
            "annual" if selected == "http_failure" else selected])
        payload["cik"] = cik
        reply = Response(payload, status_code=upstream["http_cases"]["server_error"]["status_code"]
                         if selected == "http_failure" else 200)
        monkeypatch.setattr(producer._dc, "http_get", lambda *_a, **_k: reply)
        producer._dc._one_concept(cik, upstream["query"]["concept"], asof=upstream["query"]["asof"])
        submissions = {**upstream["submissions"]["valid"], "cik": cik}
        monkeypatch.setattr(producer, "http_get", lambda *_a, **_k: Response(submissions))
        _, sic_completion = producer._sic_observation(cik)
        data = deepcopy(sample["pull_data"])
        data.update(ticker=ticker, cik=cik, source_observations={"sic": sic_completion})
        return data

    monkeypatch.setattr(producer, "pull", pull)
    output, aggregate = producer.run_batch(path, pull_date=sample["verdict_date"])
    outcomes = json.loads(output.read_text(encoding="utf-8"))["all"]
    assert [row["data_status"] for row in outcomes] == [expected, "complete"]
    first = output.parent / outcomes[0]["artifact"]
    data = json.loads(first.read_text(encoding="utf-8"))
    financial = data["source_observations"]["financials"]
    assert len(financial["upstream"]) == 1
    assert financial["upstream"][0]["request"]["cik"] == sample["survivor_rows"][0]["cik"]
    receipt = stages.read_stage_receipt(first, 1)
    assert receipt["status"] == expected
    assert receipt["reasons"] == []
    assert receipt["upstream"][1] == financial
    candidates, _, _, reconstructed = producer._read_data_results(path)
    assert [row["data_status"] for row in candidates] == [expected, "complete"]
    assert reconstructed["status"] == aggregate["status"]


def test_observed_sic_failure_cannot_be_hidden_by_financial_payload(
        monkeypatch, runtime, sample, upstream):
    path = survivors(runtime, sample)

    def pull(ticker, cik):
        payload = {**upstream["concept_envelopes"]["annual"], "cik": cik}
        monkeypatch.setattr(producer._dc, "http_get", lambda *_a, **_k: Response(payload))
        producer._dc._one_concept(cik, upstream["query"]["concept"], asof=upstream["query"]["asof"])
        monkeypatch.setattr(producer, "http_get", lambda *_a, **_k: Response(
            status_code=upstream["http_cases"]["server_error"]["status_code"]))
        _, sic_completion = producer._sic_observation(cik)
        data = deepcopy(sample["pull_data"])
        data.update(ticker=ticker, cik=cik, source_observations={"sic": sic_completion})
        return data

    monkeypatch.setattr(producer, "pull", pull)
    output, _ = producer.run_batch(path, pull_date=sample["verdict_date"])
    outcomes = json.loads(output.read_text(encoding="utf-8"))["all"]
    assert all(row["data_status"] == "partial" for row in outcomes)
    receipt = stages.read_stage_receipt(output.parent / outcomes[0]["artifact"], 1)
    assert receipt["reasons"] == []
    assert [row["status"] for row in receipt["upstream"][-2:]] == ["complete", "unavailable"]
    producer._read_data_results(path)
