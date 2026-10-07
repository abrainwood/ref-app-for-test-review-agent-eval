import json
import logging
from pathlib import Path

import pytest

import grade

SCHEMA = json.loads((Path(__file__).resolve().parent.parent / "findings.schema.json").read_text())


def good():
    return {"file": "tests/x.py", "test": "test_x", "tier": "P1", "category": "c", "summary": "s"}


def test_a_well_formed_document_validates():
    grade.validate({"findings": [good(), {**good(), "test": None}]}, SCHEMA)


def test_an_empty_findings_list_is_valid():
    grade.validate({"findings": []}, SCHEMA)


@pytest.mark.parametrize("doc, message", [
    ([], "top level"),
    ({}, "top level"),
    ({"findings": "nope"}, "top level"),
    ({"findings": [], "extra": 1}, "unexpected top-level key 'extra'"),
    ({"findings": ["text"]}, "findings[0] is not an object"),
    ({"findings": [{k: v for k, v in good().items() if k != "tier"}]}, "missing 'tier'"),
    ({"findings": [{**good(), "tier": "P9"}]}, "invalid tier 'P9'"),
    ({"findings": [{**good(), "file": 7}]}, "file must be a string"),
    ({"findings": [{**good(), "category": None}]}, "category must be a string"),
    ({"findings": [{**good(), "summary": ["x"]}]}, "summary must be a string"),
    ({"findings": [{**good(), "test": 3}]}, "test must be a string or null"),
])
def test_invalid_documents_are_rejected_with_a_specific_message(doc, message):
    with pytest.raises(grade.InvalidFindings, match=message.replace("[", r"\[").replace("]", r"\]")):
        grade.validate(doc, SCHEMA)


def test_extra_keys_in_a_finding_are_accepted_and_logged_as_a_warning(caplog):
    with caplog.at_level(logging.WARNING):
        grade.validate({"findings": [{**good(), "line": 12}]}, SCHEMA)

    assert [(r.levelname, "line" in r.getMessage() and "findings[0]" in r.getMessage()) for r in caplog.records] == [
        ("WARNING", True)]


def test_a_well_formed_finding_logs_no_warning(caplog):
    with caplog.at_level(logging.WARNING):
        grade.validate({"findings": [good()]}, SCHEMA)

    assert caplog.records == []


def test_extra_keys_do_not_excuse_a_missing_required_key():
    with pytest.raises(grade.InvalidFindings, match="missing 'tier'"):
        grade.validate({"findings": [{"file": "x", "test": None, "category": "c", "summary": "s", "line": 1}]}, SCHEMA)
