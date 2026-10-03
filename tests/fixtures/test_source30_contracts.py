"""Generated Source30 prompt provenance contracts; no provider calls."""
import json
from pathlib import Path
import re
import pytest
from make_fixtures import source30_scenarios

CASE = source30_scenarios()
ROOT = Path(__file__).resolve().parents[2]

def _recall_messages(source):
    block = source.split("const recallSource = c => {", 1)[1].split("\n}", 1)[0]
    pairs = re.findall(r'case "([^"]+)": return ("(?:\\.|[^"\\])*")', block)
    messages = {channel: json.loads(raw) for channel, raw in pairs}
    assert len(pairs) == len(messages) == 4
    raw_default, = re.findall(r'default: return ("(?:\\.|[^"\\])*")', block)
    messages["unknown"] = json.loads(raw_default)
    assert set(messages) == set(CASE["channels"])
    return messages

def _assert_source_neutral(message):
    assert not any(form in message for form in CASE["forms"])
    assert not re.search(r"\bItem\s+[14]\b", message, re.IGNORECASE)

def _blurb_parts(source):
    block = source.split("  const blurbSection = hasBlurb\n", 1)[1].split("\n\n", 1)[0]
    provided, missing = block.split("\n", 1)
    return {"provided": provided, "missing": missing}

@pytest.mark.parametrize("workflow", CASE["workflows"], ids=lambda case: case["path"])
@pytest.mark.parametrize("channel", CASE["channels"])
def test_discovery_channel_does_not_invent_a_filing_form(workflow, channel):
    source = (ROOT / workflow["path"]).read_text(encoding="utf-8")
    message = _recall_messages(source)[channel]
    _assert_source_neutral(message)
    assert workflow["generic_source"] in message
    if channel in ("sic", "sic_reverse", "both"):
        assert "SIC" in message

@pytest.mark.parametrize("part", ["provided", "missing"])
def test_business_excerpt_prompt_does_not_invent_a_form_or_item(part):
    source = (ROOT / CASE["theme_gate"]).read_text(encoding="utf-8")
    message = _blurb_parts(source)[part]
    _assert_source_neutral(message)
    assert "SEC filing" in message
    if part == "provided":
        assert "c.business_blurb.slice(0, 2000)" in message
        assert "PRIMARY" in message
    else:
        assert "No SEC filing" in message

def test_business_excerpt_description_keeps_the_same_source_contract():
    source = (ROOT / CASE["theme_gate"]).read_text(encoding="utf-8")
    metadata = source.split("const invalidInput", 1)[0]
    comment = source.split("  // business_blurb:", 1)[1].split("  const hasBlurb", 1)[0]
    _assert_source_neutral(metadata)
    _assert_source_neutral(comment)
    assert "SEC filing" in metadata
    assert "SEC filing" in comment
