"""Versioned, inert diagnostic-signal handoff from finalization to tracking."""
from __future__ import annotations
from datetime import date
import hashlib
import json
import re


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def validate_signal_snapshot(snapshot, ticker, cik, verdict_date):
    """Check claimed identity and signal integrity; retain unverified source metadata.

    This standalone handoff does not read the referenced deepdive artifact. Its
    signal digest detects payload changes, not source authenticity. Legacy v1
    snapshots without a verification label are explicitly marked unverified.
    """
    if snapshot is None:
        return None
    if not isinstance(snapshot, dict) or type(snapshot.get("schema_version")) is not int or snapshot["schema_version"] != 1:
        raise ValueError("Invalid signals snapshot schema")
    if snapshot.get("diagnostic_only") is not True or snapshot.get("never_affects_buy") is not True:
        raise ValueError("Invalid signals firewall")
    if (snapshot.get("ticker") != str(ticker).strip().upper()
            or snapshot.get("cik") != cik or snapshot.get("verdict_date") != verdict_date):
        raise ValueError("Signals snapshot identity mismatch")
    try:
        if date.fromisoformat(verdict_date).isoformat() != verdict_date:
            raise ValueError("Invalid signals date")
    except (ValueError, TypeError):
        raise ValueError("Invalid signals date") from None
    verification = snapshot.get("source_verification", "retained_unverified")
    if verification != "retained_unverified":
        raise ValueError("Signals source verification must remain retained_unverified")
    source = snapshot.get("source")
    if (not isinstance(source, dict) or not isinstance(source.get("artifact"), str)
            or not re.fullmatch(r"deepdive_[A-Za-z0-9._-]+\.json", source["artifact"])
            or type(source.get("bytes")) is not int or source["bytes"] <= 0
            or not re.fullmatch(r"[0-9a-f]{64}", str(source.get("sha256", "")))):
        raise ValueError("Invalid signals source metadata")
    payload = snapshot.get("signals")
    if not isinstance(payload, dict) or not payload:
        raise ValueError("Invalid signals payload")
    meta = payload.get("signals_meta")
    if (not isinstance(meta, dict) or meta.get("diagnostic_only") is not True
            or meta.get("never_affects_buy") is not True):
        raise ValueError("Invalid source signals firewall")
    try:
        digest = hashlib.sha256(_canonical(payload)).hexdigest()
    except (ValueError, TypeError):
        raise ValueError("Invalid signals JSON payload") from None
    if digest != snapshot.get("signals_sha256"):
        raise ValueError("Signals payload digest mismatch")
    normalized = json.loads(_canonical(snapshot))
    normalized["source_verification"] = "retained_unverified"
    return normalized


def snapshot_from_deep(deep, ticker, verdict_date, source):
    """Retain diagnostic signals and the producer-supplied source descriptor.

    Finalization supplies a descriptor from its captured deepdive bytes. This
    standalone snapshot retains that claim; recording does not re-prove it.
    """
    signals = deep.get("signals")
    if signals is None or signals == {}:
        return None
    if str(deep.get("ticker", "")).strip().upper() != str(ticker).strip().upper():
        raise ValueError("Signals source ticker mismatch")
    cik = str(deep["cik"]) if deep.get("cik") else None
    snapshot = {"schema_version": 1, "ticker": str(ticker).strip().upper(), "cik": cik,
                "verdict_date": verdict_date, "source": source,
                "source_verification": "retained_unverified",
                "diagnostic_only": True, "never_affects_buy": True,
                "signals": signals, "signals_sha256": hashlib.sha256(_canonical(signals)).hexdigest()}
    return validate_signal_snapshot(snapshot, ticker, cik, verdict_date)
