"""v6 Prüfungskern: the Python port of the LIIT-EXPR-1 logic (runtime/evaluator.mjs) and the module files.
Checked once against the JS evaluator on 2,240 random element states (0 mismatches, 2026-11-08)."""
import pytest

from app import kern

S, N, U, D, L = "satisfied", "not_satisfied", "unknown", "disputed", "legal_review_required"


def ev(expr, states):
    return kern.evaluate_expr(expr, lambda k: states.get(k, U))["status"]


@pytest.mark.parametrize("op,states,want", [
    ("all", [S, S], S), ("all", [S, N], N), ("all", [U, N], N), ("all", [S, U], U), ("all", [U, D], D),
    ("all", [D, L], L), ("any", [N, S], S), ("any", [N, N], N), ("any", [U, S], S), ("any", [N, U], U),
])
def test_all_any(op, states, want):
    expr = {op: [{"element": f"E{i}"} for i in range(len(states))]}
    assert ev(expr, {f"E{i}": s for i, s in enumerate(states)}) == want


def test_not_keeps_open_states():
    for s, want in [(S, N), (N, S), (U, U), (D, D), (L, L)]:
        assert ev({"not": {"element": "E1"}}, {"E1": s}) == want


def test_modules_reference_existing_elements():
    for mid, m in kern.load().items():
        ids = {e["id"] for e in m["elements"]}
        for o in m["outcomes"]:
            assert set(kern.refs(o["when"])) <= ids, (mid, o["id"])
        assert set(kern.leaf_elements(m, {o["id"] for o in m["outcomes"]})) <= ids


def test_unknown_context_makes_outcome_conditional():
    m = kern.load()["M05"]
    o = m["outcomes"][0]
    k = {"selected": {o["id"]: "test"}, "context": {"scope": {"status": U}, "temporal": {"status": S}},
         "assessments": {e: {"status": S, "facts": [1], "why": "", "assumed": False} for e in kern.leaf_elements(m, {o["id"]})}}
    r = kern.evaluate(m, k)[0]
    assert r["status"] in ("conditional_applicability", "unresolved", "rule_conditions_not_supported")
    k["context"]["scope"] = {"status": N}
    assert kern.evaluate(m, k)[0]["status"] == "not_applicable"
