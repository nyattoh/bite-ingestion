"""Negative controls: proof that the instrument reports failure as failure.

These cases exist to falsify the measurement, not to make BITE look good. Each
one loses required evidence (or provenance) for a reason a human can state in
one sentence, against the **unmodified** profiler, policy and operators.

What must be visible in the numbers:

============================  ===========================================
evidence removed from view    ``recall_vis`` drops below 1.0
removed but placed in R       ``recall_rec`` stays 1.0
actually fetched back         ``recall_vis`` returns to 1.0, T_rebite > 0
in R but never fetched        ``recall_vis`` stays low, T_rebite == 0
origin not recorded           ``provenance`` drops below 1.0, on every arm
============================  ===========================================

Assertions are unconditional: a guarded assertion cannot detect the regression
it guards.
"""

from __future__ import annotations

import pytest

from bite_eval.arm_runtime import attach_morphology
from bite_eval.baselines import get_baseline
from bite_eval.phase1_matrix import (
    NEGATIVE_EXPECTATIONS,
    PHASE1_ARMS,
    negative_control_report,
    run_phase1_matrix,
    validate_matrix_doc,
)
from bite_eval.pilot.families import (
    NEGATIVE_FAMILIES,
    NEGATIVE_FAMILY_INTENT,
    SYNTHETIC_FAMILIES,
    generate_family_instances,
    generate_negative_instances,
)
from bite_ingestion.packet_contract import (
    assert_evidence_ids_resolve,
    root_ids_of,
    validate_units,
)


def _matrix():
    return run_phase1_matrix(n_per_family=1, artifact_path=None)


def _rows_for(doc, family: str) -> dict[str, dict]:
    return {
        str(r["method"]): r for r in doc["rows"] if str(r["case_id"]).rsplit("-", 1)[0] == family
    }


def _r_unit_ids(out) -> list[str]:
    return [str(e["unit_id"]) for e in (out.get("R") or {}).get("entries", []) if e.get("unit_id")]


def _roots(unit_ids, out) -> set[str]:
    """Resolve ids to source units the way metrics_from_transformed does.

    CUT gives its children fresh ids, so gold ids survive only through
    ``parent_unit_id``. Comparing raw ids would be wrong.
    """
    lineage = list(out.get("units") or [])
    for e in (out.get("R") or {}).get("entries", []):
        extra = e.get("extra") or {}
        lineage.append(
            {
                "unit_id": e.get("unit_id"),
                "parent_unit_id": extra.get("parent_unit_id") or e.get("parent_unit_id"),
            }
        )
    return set(unit_ids) | root_ids_of(list(unit_ids), lineage)


# ===========================================================================
# The controls are separate from the workload
# ===========================================================================


def test_negative_families_are_not_workload_families() -> None:
    """Adding controls must not alter the workload set."""
    assert len(SYNTHETIC_FAMILIES) == 8
    assert not (set(NEGATIVE_FAMILIES) & set(SYNTHETIC_FAMILIES))
    for family in NEGATIVE_FAMILIES:
        assert family in NEGATIVE_FAMILY_INTENT, f"{family} has no stated intent"
        assert generate_family_instances(family, 1) == []


def test_workload_documents_were_not_modified() -> None:
    """Spot-check that existing families were not retuned to fit results."""
    expected = {
        "clean_local": (
            "Section A. The codeword K00 equals 100. "
            "Section B filler about weather and unrelated notes."
        ),
        "dense_cross_reference": "[1] see [2]. [2] defines K00. [3] K00=100. [4] cites [3].",
        "dependency_chain": (
            "unit_u0 depends_on=u1\nunit_u1 depends_on=u2\nunit_u2 fact=K00=100\n"
        ),
    }
    for family, doc in expected.items():
        assert generate_family_instances(family, 1)[0]["document"] == doc, family


@pytest.mark.parametrize("family", NEGATIVE_FAMILIES)
def test_negative_packets_satisfy_the_packet_contract(family: str) -> None:
    for packet in generate_negative_instances(family, 2):
        doc = str(packet["document"])
        validate_units(packet["units"], document=doc)
        assert_evidence_ids_resolve(list(packet["gold_evidence_ids"]), packet["units"])
        assert packet["gold_evidence_ids"], "a control needs required evidence"
        assert packet["recoverable_evidence_ids"] == []
        assert packet["negative_control"] is True


# ===========================================================================
# The controls run through the same matrix, same four arms
# ===========================================================================


def test_controls_are_in_the_same_matrix_with_all_four_arms() -> None:
    doc = _matrix()
    for family in NEGATIVE_FAMILIES:
        rows = _rows_for(doc, family)
        assert set(rows) == set(PHASE1_ARMS), (family, sorted(rows))
        for row in rows.values():
            assert row["case_kind"] == "negative_control"
            assert row["status"] != "failed", row


def test_controls_do_not_pollute_workload_numbers() -> None:
    doc = _matrix()
    s = doc["summary"]
    assert s["n_negative_control_rows"] == len(NEGATIVE_FAMILIES) * len(PHASE1_ARMS)
    assert s["n_total"] == s["n_workload_rows"] + s["n_negative_control_rows"]
    # Workload means must be unchanged by the presence of failing controls.
    assert s["mean_evidence_recall_visible"] == 1.0
    assert s["mean_evidence_recall_recoverable"] == 1.0
    assert s["mean_provenance"] == 1.0
    # Arm differentiation still describes the workload only.
    assert all(not str(c).startswith("neg_") for c in s["length_vs_rule_diff_families"]), s[
        "length_vs_rule_diff_families"
    ]


# ===========================================================================
# 1. Evidence removed from view -> recall actually drops
# ===========================================================================


def test_quarantined_gold_lowers_visible_recall() -> None:
    """Half the required evidence is quarantined, so recall_vis must be 0.5."""
    rows = _rows_for(_matrix(), "neg_gold_quarantined")

    # Arms that never quarantine keep everything.
    assert rows["raw_full"]["evidence_recall_visible"] == 1.0
    assert rows["length_pi"]["evidence_recall_visible"] == 1.0

    # The arm that runs UNTANGLE loses half of it — and says so.
    assert rows["rule_pi"]["evidence_recall_visible"] == 0.5, rows["rule_pi"]
    assert "UNTANGLE" in rows["rule_pi"]["operator_sequence"]


def test_lost_evidence_is_still_tracked_in_R() -> None:
    rows = _rows_for(_matrix(), "neg_gold_quarantined")
    rule = rows["rule_pi"]
    assert rule["evidence_recall_recoverable"] == 1.0
    assert rule["recoverable_evidence_ids"], "the omitted unit must be in R"

    # CUT renames units, so the R entry carries a derived id. It must still
    # resolve to the gold unit through parent_unit_id — the same lineage walk
    # the metric performs. A fresh unrelated hash would break recoverable recall.
    packet = generate_negative_instances("neg_gold_quarantined", 1)[0]
    prepared, _ = attach_morphology(packet)
    out = dict(
        get_baseline("rule_pi").run(
            prepared, {"domain": packet["domain"], "query": packet["query"]}
        )
    )
    gold = set(packet["gold_evidence_ids"])
    assert gold & _roots(_r_unit_ids(out), out), (
        "R entries must resolve to gold through lineage",
        gold,
        _r_unit_ids(out),
    )


# ===========================================================================
# 2. R vs an actual recovery must be distinguishable in the numbers
# ===========================================================================


def test_rebite_recovers_and_is_billed() -> None:
    rows = _rows_for(_matrix(), "neg_gold_quarantined")
    rule, rebite = rows["rule_pi"], rows["rule_pi_rebite"]

    # Same routing decision — the only difference is bounded recovery.
    assert rule["operator_sequence"] == rebite["operator_sequence"]

    # Recovery restores visible recall...
    assert rule["evidence_recall_visible"] == 0.5
    assert rebite["evidence_recall_visible"] == 1.0
    # ...and is not free.
    assert int(rule["T_rebite"]) == 0
    assert int(rebite["T_rebite"]) > 0, rebite
    assert int(rebite["T_total"]) > int(rule["T_total"]) - 1  # recovery adds cost, never removes


def test_in_R_is_not_the_same_as_recovered() -> None:
    """Bounded recovery is targeted, not omniscient.

    The surviving text repeats the query's fields, so no fetch request can be
    formed. The evidence stays in R and visible recall stays down even for the
    re-bite arm.
    """
    rows = _rows_for(_matrix(), "neg_unrecoverable_gold")
    rule, rebite = rows["rule_pi"], rows["rule_pi_rebite"]

    assert rule["evidence_recall_visible"] == 0.5
    assert rebite["evidence_recall_visible"] == 0.5, rebite
    assert int(rebite["T_rebite"]) == 0, "nothing was fetched, so nothing may be billed"
    # Recoverable recall still credits R: the unit was not silently destroyed.
    assert rule["evidence_recall_recoverable"] == 1.0
    assert rebite["evidence_recall_recoverable"] == 1.0


def test_the_two_controls_differ_only_in_recoverability() -> None:
    """Same loss, different outcome — that contrast is the point."""
    doc = _matrix()
    a = _rows_for(doc, "neg_gold_quarantined")["rule_pi_rebite"]
    b = _rows_for(doc, "neg_unrecoverable_gold")["rule_pi_rebite"]
    assert a["evidence_recall_visible"] == 1.0
    assert b["evidence_recall_visible"] == 0.5
    assert int(a["T_rebite"]) > 0
    assert int(b["T_rebite"]) == 0


# ===========================================================================
# 3. Provenance deficit
# ===========================================================================


def test_missing_provenance_lowers_the_score_on_every_arm() -> None:
    rows = _rows_for(_matrix(), "neg_missing_provenance")
    for arm in PHASE1_ARMS:
        assert rows[arm]["provenance"] == 0.5, (arm, rows[arm]["provenance"])
    # The source defect, not the arm, is what moved the number.
    assert len({r["provenance"] for r in rows.values()}) == 1


def test_missing_provenance_does_not_look_like_evidence_loss() -> None:
    """A provenance defect must not be reported as a recall defect."""
    rows = _rows_for(_matrix(), "neg_missing_provenance")
    for arm in PHASE1_ARMS:
        assert rows[arm]["evidence_recall_visible"] == 1.0
        assert rows[arm]["evidence_recall_recoverable"] == 1.0


# ===========================================================================
# The artifact enforces all of this
# ===========================================================================


def test_matrix_artifact_reports_controls_and_passes_validation() -> None:
    doc = _matrix()
    report = doc["negative_control_report"]
    assert report["n_checked"] == len(NEGATIVE_EXPECTATIONS)
    assert report["violations"] == [], report["violations"]
    assert set(report["observed"]) == set(NEGATIVE_FAMILIES)
    assert validate_matrix_doc(doc) == []


def test_validator_rejects_a_control_that_stopped_reporting_failure() -> None:
    """Tamper check: if a control silently starts passing, validation fails."""
    doc = _matrix()
    for row in doc["rows"]:
        if str(row["case_id"]).startswith("neg_gold_quarantined") and row["method"] == "rule_pi":
            row["evidence_recall_visible"] = 1.0  # pretend nothing was lost
    doc["negative_control_report"] = negative_control_report(doc["rows"])
    errs = validate_matrix_doc(doc)
    assert any("did not report the failure" in e for e in errs), errs


def test_controls_are_deterministic() -> None:
    a = negative_control_report(_matrix()["rows"])
    b = negative_control_report(_matrix()["rows"])
    assert a["observed"] == b["observed"]


@pytest.mark.parametrize("family", NEGATIVE_FAMILIES)
def test_each_control_states_why_it_must_fail(family: str) -> None:
    intent = NEGATIVE_FAMILY_INTENT[family]
    assert len(intent) > 80, "the reason must be readable by a human, not a code comment"
    assert any(k in intent for k in ("recall_vis", "recall_rec", "provenance")), intent


def test_direct_adapter_call_matches_the_matrix() -> None:
    """The numbers are not an artifact of the matrix harness."""
    packet = generate_negative_instances("neg_gold_quarantined", 1)[0]
    prepared, _ = attach_morphology(packet)
    out = dict(
        get_baseline("rule_pi").run(
            prepared, {"domain": packet["domain"], "query": packet["query"]}
        )
    )
    assert out["status"] == "ok"
    gold = set(packet["gold_evidence_ids"])
    # Resolve through lineage: CUT renames units before UNTANGLE sees them.
    visible_roots = _roots(out["visible_unit_ids"], out)
    r_roots = _roots(_r_unit_ids(out), out)
    assert len(gold & visible_roots) == 1, ("exactly one gold unit survives", gold, visible_roots)
    assert gold & r_roots, ("the other one is in R", gold, r_roots)
    assert not (gold & visible_roots & r_roots), "a gold unit cannot be both visible and in R"
