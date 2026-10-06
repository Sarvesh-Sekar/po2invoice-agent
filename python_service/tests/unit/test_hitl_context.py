"""Serialization contract for the persisted HITL context blob."""

from __future__ import annotations

from app.helpers.hitl_context import interrupt_hitl_payload, parse_hitl_context


def test_interrupt_payload_projects_question_and_context() -> None:
    hint = {
        "question": "create_customer",
        "run_id": "r1",
        "context": {"customer_name": "Acme Ltd.", "customer_code": None},
    }
    payload = interrupt_hitl_payload(hint)
    assert payload == {
        "question": "create_customer",
        "context": {"customer_name": "Acme Ltd.", "customer_code": None},
    }


def test_interrupt_payload_tolerates_malformed_hint() -> None:
    assert interrupt_hitl_payload(None) == {"question": None, "context": {}}
    assert interrupt_hitl_payload("raw") == {"question": None, "context": {}}
    assert interrupt_hitl_payload(["not", "a", "dict"]) == {"question": None, "context": {}}


def test_parse_round_trips_new_blob() -> None:
    raw = '{"question": "create_customer", "context": {"customer_name": "Acme Ltd."}}'
    parsed = parse_hitl_context(raw)
    assert parsed["question"] == "create_customer"
    assert parsed["context"] == {"customer_name": "Acme Ltd."}


def test_parse_understands_legacy_bare_context_blob() -> None:
    parsed = parse_hitl_context('{"po_number": "PO-1001", "issues": []}')
    assert parsed["question"] is None
    assert parsed["context"] == {"po_number": "PO-1001", "issues": []}


def test_parse_tolerates_bad_json_and_none() -> None:
    assert parse_hitl_context(None) == {"question": None, "context": {}}
    assert parse_hitl_context("not-json") == {"question": None, "context": {}}
    assert parse_hitl_context("[1, 2, 3]") == {"question": None, "context": {}}
