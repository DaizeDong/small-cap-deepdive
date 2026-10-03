"""Bind event discovery to mandatory cheap-pass decisions without a theme-fit gate."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from pathlib import Path

from filter_by_sic import (stage_completion, stage_work, _valid_completion,
                           prepare_stage_output, write_stage_receipt, stage_receipt_path)

EVENT_ARTIFACT = "candidates_event_admitted.json"
EVENT_STAGES = {"event_spinoffs": "spinoff", "event_insider_clusters": "insider_cluster"}
IDENTITY_KEYS = ("input_index", "ticker", "cik", "band")


def artifact_snapshot(path):
    """Bind the same bytes that callers parse."""
    path = Path(path)
    raw = path.read_bytes()
    binding = {"artifact": path.name, "artifact_bytes": len(raw),
               "artifact_sha256": hashlib.sha256(raw).hexdigest(),
               "run_dir": str(path.resolve().parent)}
    return raw, binding


def artifact_binding(path):
    return artifact_snapshot(path)[1]


def validate_event_receipt(record, binding, row_count):
    """Validate a parsed receipt against the consumed payload snapshot."""
    if (not _valid_completion(record) or record["row_count"] != row_count
            or any(record.get(key) != value for key, value in binding.items())):
        raise ValueError("Event receipt does not bind the consumed bytes")
    return record


def _snapshot_receipt(path, binding, row_count):
    raw = stage_receipt_path(path).read_bytes()
    try:
        record = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError):
        raise ValueError("Event receipt is invalid") from None
    return validate_event_receipt(record, binding, row_count), raw


def _revalidate_snapshot(path, binding, receipt_raw):
    if (artifact_binding(path) != binding
            or stage_receipt_path(path).read_bytes() != receipt_raw):
        raise ValueError("Event evidence changed during validation")


def bound_artifact(directory, binding):
    if not isinstance(binding, dict):
        raise ValueError("Event input binding is missing")
    name = binding.get("artifact")
    if (not isinstance(name, str) or not name or name in {".", ".."}
            or "/" in name or "\\" in name or ":" in name):
        raise ValueError("Event input must be a same-directory artifact")
    path = Path(directory) / name
    if artifact_binding(path) != binding:
        raise ValueError("Event input bytes or directory changed")
    return path


def event_admission(source_rows, source_completion, cheap_completion, source_binding, cheap_binding,
                    screened_rows):
    """Reconstruct every event decision from exact source and screening receipts."""
    if not isinstance(source_rows, list):
        raise ValueError("Event candidates must be a list")
    event_type = EVENT_STAGES.get(source_completion.get("stage"))
    if event_type is None or source_completion.get("row_count") != len(source_rows):
        raise ValueError("Event discovery receipt has the wrong source or cohort")
    if (cheap_completion.get("stage") != "cheap_pass"
            or cheap_completion.get("input") != source_binding
            or cheap_completion.get("input_count") != len(source_rows)):
        raise ValueError("Cheap-pass evidence is not bound to this event cohort")
    if source_binding.get("run_dir") != cheap_binding.get("run_dir"):
        raise ValueError("Event discovery and screening must share one run")
    decisions = cheap_completion.get("decisions")
    if not isinstance(decisions, list) or len(decisions) != len(source_rows):
        raise ValueError("Every event input requires one screening decision")
    indexed = {}
    for decision in decisions:
        index = decision.get("input_index") if isinstance(decision, dict) else None
        if type(index) is not int or not 0 <= index < len(source_rows) or index in indexed:
            raise ValueError("Event screening index is invalid or duplicated")
        indexed[index] = decision
    scored = {}
    for row in screened_rows:
        index_text = str(row.get("input_index", ""))
        if re.fullmatch(r"[0-9]+", index_text) is None:
            raise ValueError("Cheap-pass row input index is invalid")
        index = int(index_text)
        if index not in indexed or index in scored:
            raise ValueError("Cheap-pass row index is unknown or duplicated")
        decision = indexed[index]
        if (row.get("ticker") != decision.get("ticker")
                or row.get("cik") != decision.get("cik")
                or str(row.get("rejected")).lower() not in {"true", "false"}
                or decision.get("screening_decision") != (
                    "rejected_existing_policy" if str(row["rejected"]).lower() == "true" else "retained")):
            raise ValueError("Cheap-pass row disagrees with its decision")
        if decision.get("evidence_complete") is True and (
                str(row.get("kf_scanned")).lower() != "true"
                or str(row.get("disclosure_review_required")).lower() != "false"):
            raise ValueError("Complete event screening requires observed kill-flag evidence")
        scored[index] = row
    expected_scored = {index for index, decision in indexed.items()
                       if decision.get("screening_decision") in {"retained", "rejected_existing_policy"}}
    if set(scored) != expected_scored:
        raise ValueError("Cheap-pass rows do not cover the scored decisions")
    outcomes, survivors, work, reasons, identities = [], [], [], [], set()
    for index, source in enumerate(source_rows):
        if not isinstance(source, dict):
            raise ValueError("Event candidate must be an object")
        ticker, cik = source.get("ticker"), source.get("cik")
        if (not isinstance(ticker, str) or not isinstance(cik, str) or not (ticker or cik)
                or (ticker and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{0,31}", ticker) is None)
                or (cik and (re.fullmatch(r"[0-9]{1,10}", cik) is None or int(cik) == 0))
                or source.get("event_type") != event_type
                or not isinstance(source.get("name"), str) or not source["name"].strip()
                or not isinstance(source.get("catalyst"), str) or not source["catalyst"].strip()
                or source.get("band") not in {"deep", "watch", "large", "unknown"}):
            raise ValueError("Event identity, source, catalyst or band is invalid")
        label = ticker.upper() if ticker else "CIK" + cik.lstrip("0")
        if label in identities:
            raise ValueError("Event output identity is duplicated")
        identities.add(label)
        decision = indexed[index]
        if (decision.get("ticker") != ticker or decision.get("cik") != cik
                or decision.get("band") not in {"deep", "watch", "large", "unknown"}):
            raise ValueError("Event screening identity or band changed")
        screening = decision.get("screening_decision")
        if screening not in {"retained", "rejected_existing_policy", "excluded_existing_large_band",
                             "not_processed_limit", "unavailable"}:
            raise ValueError("Event screening decision is invalid")
        complete = decision.get("evidence_complete") is True
        if screening == "excluded_existing_large_band":
            if decision["band"] != "large" or source["band"] != "large":
                raise ValueError("Event size exclusion requires the large band")
            disposition, status = "excluded", "complete"
        elif screening in {"retained", "rejected_existing_policy"} and complete:
            disposition = "retained" if screening == "retained" else "rejected"
            status = "complete"
        else:
            disposition, status = "unresolved", "unavailable"
        row = {**source, "input_index": index, "source_band": source["band"],
               "band": decision["band"], "admission_decision": disposition,
               "screening_decision": screening, "screening_evidence_complete": complete}
        outcomes.append(row)
        if not ticker or not cik:
            reasons.append("unresolved_event_identity")
        if disposition in {"retained", "unresolved"}:
            survivors.append(row)
            if row["band"] == "unknown":
                reasons.append("unresolved_candidate_band")
        work.append(stage_work("event_cheap_pass", label, index, status=status,
                               reason="" if status == "complete" else "incomplete_event_screening"))
    completion = stage_completion("event_admission", len(survivors), work=work,
                                  upstream=[source_completion, cheap_completion],
                                  reasons=sorted(set(reasons)))
    completion.update(input=source_binding, cheap_input=cheap_binding, decisions=outcomes,
                      policy="event-source-and-cheap-pass-v1", theme_fit_required=False)
    return survivors, completion


def _event_inputs(source_path, cheap_path):
    source_path, cheap_path = Path(source_path), Path(cheap_path)
    if source_path.resolve().parent != cheap_path.resolve().parent:
        raise ValueError("Event evidence must be in one run directory")
    source_raw, source_binding = artifact_snapshot(source_path)
    cheap_raw, cheap_binding = artifact_snapshot(cheap_path)
    rows = json.loads(source_raw.decode("utf-8"))
    if not isinstance(rows, list):
        raise ValueError("Event source must contain a candidate list")
    screened = list(csv.DictReader(io.StringIO(cheap_raw.decode("utf-8"), newline="")))
    source, source_receipt_raw = _snapshot_receipt(source_path, source_binding, len(rows))
    cheap, cheap_receipt_raw = _snapshot_receipt(cheap_path, cheap_binding, len(screened))
    survivors, completion = event_admission(rows, source, cheap, source_binding, cheap_binding, screened)
    _revalidate_snapshot(source_path, source_binding, source_receipt_raw)
    _revalidate_snapshot(cheap_path, cheap_binding, cheap_receipt_raw)
    completion["source_receipt_sha256"] = hashlib.sha256(source_receipt_raw).hexdigest()
    completion["cheap_receipt_sha256"] = hashlib.sha256(cheap_receipt_raw).hexdigest()
    return survivors, completion


def write_event_admission(source_path, cheap_path):
    survivors, completion = _event_inputs(source_path, cheap_path)
    path = prepare_stage_output(Path(source_path).parent / EVENT_ARTIFACT)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(survivors, stream, ensure_ascii=False, indent=2)
    write_stage_receipt(path, completion)
    return path, completion


def read_event_admission(directory):
    directory = Path(directory)
    path = directory / EVENT_ARTIFACT
    payload, binding = artifact_snapshot(path)
    raw = json.loads(payload.decode("utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Event admission must contain a candidate list")
    receipt, receipt_raw = _snapshot_receipt(path, binding, len(raw))
    source_path = bound_artifact(directory, receipt.get("input"))
    cheap_path = bound_artifact(directory, receipt.get("cheap_input"))
    expected, completion = _event_inputs(source_path, cheap_path)
    if raw != expected or any(receipt.get(key) != value for key, value in completion.items()):
        raise ValueError("Event admission disagrees with source and cheap-pass evidence")
    _revalidate_snapshot(path, binding, receipt_raw)
    return raw, receipt


def event_input_artifacts(directory, receipt):
    """Enumerate every source/receipt byte the event reader validates."""
    directory = Path(directory)
    paths = [directory / EVENT_ARTIFACT,
             bound_artifact(directory, receipt["input"]),
             bound_artifact(directory, receipt["cheap_input"])]
    return [member for path in paths for member in (path, stage_receipt_path(path))]
