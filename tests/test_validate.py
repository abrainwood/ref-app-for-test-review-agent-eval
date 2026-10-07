import json
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
    ({"findings": [{**good(), "severity": "high"}]}, "unexpected key 'severity'"),
    ({"findings": [{**good(), "file": 7}]}, "file must be a string"),
    ({"findings": [{**good(), "category": None}]}, "category must be a string"),
    ({"findings": [{**good(), "summary": ["x"]}]}, "summary must be a string"),
    ({"findings": [{**good(), "test": 3}]}, "test must be a string or null"),
])
def test_invalid_documents_are_rejected_with_a_specific_message(doc, message):
    with pytest.raises(grade.InvalidFindings, match=message.replace("[", r"\[").replace("]", r"\]")):
        grade.validate(doc, SCHEMA)
