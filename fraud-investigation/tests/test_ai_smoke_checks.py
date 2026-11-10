"""Offline tests of the smoke-test graders and the read-only fixture tool (no model needed)."""
import pytest

from fraudinv.ai_smoke import Local, check_answer, get_case_evidence, load_case


@pytest.fixture
def case():
    return load_case()


def test_grounded_answer_passes(case):
    text = ("Case CASE-FIX-001 concerns a TRANSFER of 181,500.00 simulation currency units at step 210 [E1]. "
            "The recipient has no earlier records in this dataset [E2]. The model ranked it 3 of 50 with a "
            "ranking score of 0.87 [E3]; sender history is missing.")
    res = check_answer(text, case)
    assert res["passed"], res
    assert res["mentions_no_history"]


def test_invented_number_fails(case):
    res = check_answer("A TRANSFER of 250,000 units [E1] to a new recipient [E2].", case)
    assert not res["passed"] and 250000.0 in res["unsupported_numbers"]


def test_fraud_assertion_fails(case):
    res = check_answer("This transaction is fraud [E1] [E2].", case)
    assert not res["passed"]


def test_reasoning_in_content_fails_and_is_not_graded_as_answer(case):
    text = ("We must not claim a transaction is fraud. Maybe 999 units.\n</think>\n\n"
            "A TRANSFER of 181,500.00 units [E1]; the recipient has no earlier records [E2].")
    res = check_answer(text, case)
    assert res["reasoning_leaked_into_content"] and not res["passed"]
    assert res["unsupported_numbers"] == [] and not res["asserts_fraud_as_fact"]


def test_citation_must_name_returned_evidence(case):
    res = check_answer("TRANSFER of 181,500.00 units [E1] [E2] [E7].", case)
    assert res["invalid_citations"] == ["[E7]"] and not res["passed"]
    err = get_case_evidence({"case_id": "CASE-FIX-999"}, case)
    res = check_answer("Case not found [E1] [E2].", case, returned=err)
    assert res["invalid_citations"] == ["[E1]", "[E2]"] and not res["passed"]


def test_tool_is_typed_and_read_only(case):
    before = load_case()
    out = get_case_evidence({"case_id": "CASE-FIX-001"}, case)
    out["transaction"]["amount"] = 1.0  # mutating the returned copy
    assert case == before
    assert get_case_evidence({"case_id": "CASE-FIX-999"}, case)["error"] == "case_not_found"
    assert get_case_evidence({"case_id": "CASE-FIX-001", "sql": "drop"}, case)["error"] == "invalid_arguments"
    assert get_case_evidence({"case_id": 1}, case)["error"] == "invalid_arguments"


def test_non_local_endpoint_refused():
    with pytest.raises(ValueError, match="non-local"):
        Local("https://ollama.com", "qwen3:4b", 4096, 5)
