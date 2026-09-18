"""Phase 1 wiring: profiler → policy → operators → arms → bounded re-bite."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from bite_eval.arm_runtime import (
    FEATURE_KEYS,
    PHASE1_ARMS,
    attach_morphology,
    bounded_rebite,
    ensure_operator_packet,
    profiler_source_unit,
    run_phase1_matrix,
)
from bite_eval.baselines import get_baseline
from bite_eval.harness import EvalHarness
from bite_eval.phase1_matrix import ROW_KEYS, summarize_rows, validate_matrix_doc
from bite_eval.pilot.families import SYNTHETIC_FAMILIES, generate_family_instances
from bite_ingestion.interfaces.operator import OperatorId
from bite_ingestion.operators import apply_operator
from bite_ingestion.packet_contract import conservation_untraced, root_ids_of
from bite_ingestion.policies import apply_sequence

ARTIFACT = Path("artifacts/phase1/arm_differentiation.json")


def test_morphology_has_eight_features() -> None:
    packet = generate_family_instances("repeated_records", 1)[0]
    prepared, report = attach_morphology(packet)
    morph = prepared["morphology"]
    assert tuple(morph) == FEATURE_KEYS or set(morph) == set(FEATURE_KEYS)
    assert set(morph) == set(FEATURE_KEYS)
    assert all(isinstance(morph[k], float) for k in FEATURE_KEYS)
    assert set(report.features) == set(FEATURE_KEYS)


def test_empty_morphology_fails_closed() -> None:
    out = dict(
        get_baseline("rule_pi").run(
            {"document": "text", "query": "q", "morphology": {}},
            {"domain": "prose"},
        )
    )
    assert out["status"] == "failed"
    assert "morphology_missing" in out["reason"]
    assert out["baseline_trace"]["reason_code"] == "morphology_missing"


def test_rule_pi_sequence_varies_across_families() -> None:
    sequences: set[tuple[str, ...]] = set()
    observed_ok = False
    for family in SYNTHETIC_FAMILIES:
        raw = generate_family_instances(family, 1)[0]
        prepared, _ = attach_morphology(raw)
        out = dict(get_baseline("rule_pi").run(prepared, {"domain": prepared.get("domain")}))
        assert out["status"] == "ok", (family, out.get("reason"))
        seq = tuple(out["proposed_sequence"])
        sequences.add(seq)
        fires = (out.get("baseline_trace") or {}).get("decision") or {}
        rules = fires.get("rules_fired") or []
        assert rules, family
        for fire in rules:
            assert fire.get("observed") is not None, (family, fire)
            observed_ok = True
    assert observed_ok
    assert len(sequences) >= 2, sequences


def test_gold_and_oracle_stay_out_of_routing() -> None:
    packet = generate_family_instances("clean_local", 1)[0]
    src = profiler_source_unit(packet)
    assert set(src) <= {"payload", "text", "query"}
    assert "gold_answer" not in src
    assert "gold_evidence_ids" not in src
    assert "family" not in src
    prepared, _ = attach_morphology(packet)
    morph = prepared["morphology"]
    assert not any(str(k).startswith(("gold_", "oracle_", "eval_")) for k in morph)
    poisoned = dict(packet)
    poisoned["gold_answer"] = "SHOULD_NOT_MATTER"
    poisoned["oracle_route"] = "INTEGRATE"
    a, _ = attach_morphology(packet)
    b, _ = attach_morphology(poisoned)
    assert a["morphology"] == b["morphology"]
    out = dict(get_baseline("rule_pi").run(prepared, {"domain": "prose"}))
    decision = (out.get("baseline_trace") or {}).get("decision") or {}
    fired = str(decision.get("rules_fired"))
    assert "SHOULD_NOT_MATTER" not in fired
    assert "oracle_route" not in fired


def test_length_pi_does_not_read_morphology() -> None:
    packet = generate_family_instances("sparse_anomaly", 1)[0]
    prepared, _ = attach_morphology(packet)
    out_a = dict(get_baseline("length_pi").run(prepared, {}))
    prepared["morphology"] = {k: 1.0 for k in FEATURE_KEYS}
    out_b = dict(get_baseline("length_pi").run(prepared, {}))
    assert out_a["proposed_sequence"] == out_b["proposed_sequence"]
    notes = ((out_a.get("baseline_trace") or {}).get("decision") or {}).get("notes") or []
    assert any("morphology ignored" in str(n) for n in notes)


def test_arms_produce_distinct_payloads() -> None:
    doc = run_phase1_matrix(n_per_family=1, artifact_path=ARTIFACT)
    summary = doc["summary"]
    assert summary["raw_vs_candidate_diff_payload"] > 0
    assert summary["length_vs_rule_diff_families"], summary
    hashes_by_arm: dict[str, set[str]] = {a: set() for a in PHASE1_ARMS}
    for row in doc["rows"]:
        hashes_by_arm[str(row["method"])].add(str(row["payload_sha256"]))
    assert hashes_by_arm["raw_full"] != hashes_by_arm["length_pi"]
    assert not validate_matrix_doc(doc)


def test_no_op_recorded_in_artifact() -> None:
    doc = run_phase1_matrix(n_per_family=1, artifact_path=ARTIFACT)
    statuses = {str(row["status"]) for row in doc["rows"]}
    assert "no_op" in statuses
    assert "pass_through" in statuses
    assert "failed" not in statuses
    for row in doc["rows"]:
        if row["status"] == "no_op":
            assert row["method"] != "raw_full"
            assert row["no_op"] is True
            assert row["baseline_status"] == "ok"
        if row["status"] == "pass_through":
            assert row["method"] == "raw_full"


def test_operators_are_applied_not_just_proposed() -> None:
    packet, _ = attach_morphology(generate_family_instances("sparse_anomaly", 1)[0])
    out = dict(get_baseline("length_pi").run(packet, {}))
    assert out["proposed_sequence"]
    tau = out["tau"]
    assert any(isinstance(s, dict) and s.get("op") == "APPLY" and s.get("applied") for s in tau)
    assert out.get("transformation_status") in {"no_op", "transformed"}
    assert "R" in out


def test_cut_unit_ids_resolve_to_gold_via_parent_chain() -> None:
    packet = generate_family_instances("repeated_records", 1)[0]
    gold = list(packet["gold_evidence_ids"])
    out = apply_operator(OperatorId.CUT, packet, None)
    units = [u for u in out["units"] if isinstance(u, Mapping)]
    roots = root_ids_of([str(u["unit_id"]) for u in units], units)
    assert set(gold) <= roots
    for u in units:
        if u.get("parent_unit_id"):
            chain = root_ids_of([str(u["unit_id"])], units)
            assert chain


def test_integrate_visible_ids_match_unit_ids() -> None:
    packet = {
        "packet_id": "join",
        "visible_evidence": [
            {"text": "id=42 left"},
            {"text": "id=42 right"},
            {"text": "solo"},
        ],
        "provenance": {"unit_id": "src", "source_uri": "synthetic://join"},
    }
    out = apply_operator(OperatorId.INTEGRATE, packet, {"integrate_mode": "deterministic_join"})
    unit_ids = {str(u["unit_id"]) for u in out["units"]}
    visible_ids = {vid for item in out["visible_evidence"] for vid in item["unit_ids"]}
    assert visible_ids == unit_ids
    joined = [u for u in out["units"] if u.get("joined_from")]
    assert joined
    for u in joined:
        assert u.get("parent_unit_id")
        roots = root_ids_of([str(u["unit_id"])], out["units"])
        assert set(u["joined_from"]) <= roots


def test_operator_conservation_property() -> None:
    packet = generate_family_instances("repeated_records", 1)[0]
    input_ids = [str(u["unit_id"]) for u in packet["units"]]
    for op in (OperatorId.CUT, OperatorId.UNTANGLE, OperatorId.REDUCE, OperatorId.INTEGRATE):
        out = apply_operator(op, packet, None)
        missing = conservation_untraced(
            input_ids,
            visible_units=list(out.get("units") or []),
            r_entries=list((out.get("R") or {}).get("entries") or []),
            loss_ledger=list(out.get("irreversible_loss_ledger") or []),
        )
        assert missing == [], (op, missing)


def test_sequence_conservation_via_lineage() -> None:
    packet = generate_family_instances("malformed_mixed", 1)[0]
    input_ids = [str(u["unit_id"]) for u in packet["units"]]
    out = apply_sequence(
        (OperatorId.CUT, OperatorId.UNTANGLE, OperatorId.REDUCE),
        packet,
    )
    missing = conservation_untraced(
        input_ids,
        visible_units=list(out.get("units") or []),
        r_entries=list((out.get("R") or {}).get("entries") or []),
        loss_ledger=list(out.get("irreversible_loss_ledger") or []),
    )
    assert missing == []


def test_rule_pi_rebite_recovers_query_relevant_omission() -> None:
    packet = {
        "document": "ERROR: secret_token=ZZ9 value=42",
        "query": "What is secret_token?",
        "morphology": {
            "b": 0.2,
            "a": 0.9,
            "r": 0.0,
            "k": 0.1,
            "l": 0.5,
            "u": 0.2,
        },
    }
    out = dict(get_baseline("rule_pi_rebite").run(packet, {"domain": "prose"}))
    assert out["status"] == "ok", out.get("reason")
    assert "UNTANGLE" in out["proposed_sequence"]
    steps = (out.get("baseline_trace") or {}).get("rebite_steps") or []

    # Unconditional: recovery must actually run and must actually be billed.
    # The earlier revision accepted "or 'secret_token' in payload" and
    # asserted rebite_tokens >= 0, so it stayed green even if recovery never
    # fired. A guarded assertion cannot detect the regression it guards.
    assert steps, "bounded re-bite did not run at all"
    successes = [s for s in steps if s.get("outcome") == "success"]
    assert successes, (steps, out.get("R"))
    assert int(out["accounting"]["rebite_tokens"]) > 0, "recovered evidence must not be free"
    payload = str(out.get("payload_text") or out.get("visible_evidence") or "")
    assert "secret_token" in payload, "recovered unit must reach the payload"


def test_profiler_connected() -> None:
    h = EvalHarness(artifact_root=None, persist=False)
    packet = generate_family_instances("malformed_mixed", 1)[0]
    m = h.run_smoke("rule_pi", packet, {"domain": packet.get("domain")})
    assert m["status"] == "ok", m.get("reason")
    morph = (m.get("method_output") or {}) if isinstance(m.get("method_output"), dict) else {}
    # morphology lives on the prepared packet; sequence must not be the empty-vector constant.
    seq = morph.get("proposed_sequence") or []
    assert seq
    rows = m.get("ledger_rows") or []
    assert any(isinstance(r, dict) and r.get("category") == "profiler" for r in rows)


def test_rule_pi_rebite_matches_rule_pi_sequence() -> None:
    packet, _ = attach_morphology(generate_family_instances("sparse_anomaly", 1)[0])
    a = dict(get_baseline("rule_pi").run(packet, {}))
    b = dict(get_baseline("rule_pi_rebite").run(packet, {}))
    assert a["proposed_sequence"] == b["proposed_sequence"]


def test_rebite_bounded_and_no_repeat_fetch() -> None:
    packet = {
        "document": "ERROR: secret_token=ZZ9\nERROR: secret_token=ZZ9",
        "query": "What is secret_token?",
        "morphology": {"b": 0.2, "a": 0.9, "r": 0.9, "k": 0.1, "l": 0.2, "u": 0.2},
    }
    working = ensure_operator_packet(packet)
    from bite_ingestion.interfaces.operator import OperatorId
    from bite_ingestion.policies import apply_sequence

    transformed = apply_sequence((OperatorId.CUT, OperatorId.UNTANGLE), working)
    out, tokens, steps = bounded_rebite(
        transformed,
        query="What is secret_token?",
        original_units=[u for u in working["units"] if isinstance(u, Mapping)],
    )
    uids = [s["unit_id"] for s in steps]
    assert len(uids) == len(set(uids))
    assert len(steps) <= 3
    for step in steps:
        assert "locator" in step

    # Unconditional: this fixture is built so recovery must succeed.
    successes = [s for s in steps if s.get("outcome") == "success"]
    assert successes, steps
    assert tokens > 0
    vis_units = [u for u in (out.get("units") or []) if isinstance(u, Mapping)]
    recovered = [
        u for u in vis_units if (u.get("provenance") or {}).get("renderer_id") == "recover"
    ]
    assert recovered, "a successful fetch must add a recovered unit"
    for u in recovered:
        assert u.get("provenance", {}).get("source_uri") or u.get("source_uri")
        assert u.get("provenance", {}).get("byte_or_token_span")


def test_rebite_token_accounting_in_matrix() -> None:
    """T_rebite > 0 iff the re-bite arm's payload differs from rule_pi.

    Both directions are asserted. The earlier revision only checked the
    "payload differs -> tokens > 0" branch, which never executes on the
    current matrix (no case has query-relevant evidence in R), so the test
    was silently vacuous.
    """
    doc = run_phase1_matrix(n_per_family=1, artifact_path=None)
    checked = 0
    for row in doc["rows"]:
        if row["method"] != "rule_pi_rebite":
            continue
        rp = next(
            r for r in doc["rows"] if r["case_id"] == row["case_id"] and r["method"] == "rule_pi"
        )
        checked += 1
        t_rebite = int(row["T_rebite"] or 0)
        if row["payload_sha256"] != rp["payload_sha256"]:
            assert t_rebite > 0, row
        else:
            assert t_rebite == 0, (
                "identical payload must not be billed re-bite tokens",
                row,
            )
    assert checked > 0, "no rule_pi_rebite rows in the matrix"


def test_t_total_equals_bucket_sum() -> None:
    doc = run_phase1_matrix(n_per_family=1, artifact_path=None)
    for row in doc["rows"]:
        expected = sum(
            int(row[k] or 0)
            for k in (
                "T_profiler",
                "T_router",
                "T_operator",
                "T_target_in",
                "T_target_out",
                "T_rebite",
            )
        )
        assert int(row["T_total"] or 0) == expected
        assert row["dc_violations"] == []


def test_no_duplicate_call_id() -> None:
    doc = run_phase1_matrix(n_per_family=1, artifact_path=None)
    for row in doc["rows"]:
        ids = list(row.get("ledger_call_ids") or [])
        assert len(ids) == len(set(ids)), (row["case_id"], row["method"], ids)


def test_failed_rows_counted() -> None:
    summary = summarize_rows(
        [
            {
                "case_id": "a",
                "method": "raw_full",
                "status": "pass_through",
                "failed": False,
                "no_op": False,
            },
            {
                "case_id": "a",
                "method": "length_pi",
                "status": "failed",
                "failed": True,
                "no_op": False,
            },
            {
                "case_id": "a",
                "method": "rule_pi",
                "status": "no_op",
                "failed": False,
                "no_op": True,
            },
            {
                "case_id": "a",
                "method": "rule_pi_rebite",
                "status": "timeout",
                "failed": False,
                "no_op": False,
            },
        ]
    )
    assert summary["n_total"] == 4
    assert summary["n_failed"] == 1
    assert summary["n_no_op"] == 1
    assert summary["n_excluded"] == 1
    assert summary["n_measured"] == 3
    assert summary["failure_rate"] == 0.25


def test_same_rows_used_across_paired_comparison() -> None:
    doc = run_phase1_matrix(n_per_family=1, artifact_path=None)
    by_case: dict[str, set[str]] = {}
    for row in doc["rows"]:
        by_case.setdefault(str(row["case_id"]), set()).add(str(row["method"]))
    for cid, methods in by_case.items():
        assert methods == set(PHASE1_ARMS), cid
    assert doc["summary"]["n_paired_rows"] == doc["summary"]["n_total"]
    assert doc["summary"]["n_complete_cases"] * 4 == doc["summary"]["n_total"]


def test_metrics_come_from_transformed_state() -> None:
    doc = run_phase1_matrix(n_per_family=1, artifact_path=None)
    for row in doc["rows"]:
        for k in ROW_KEYS:
            assert k in row
        rec = row["recoverable_evidence_ids"]
        assert all(not str(x).startswith("gold_") for x in rec)
        assert 0.0 <= float(row["evidence_recall_visible"]) <= 1.0
        assert 0.0 <= float(row["provenance"]) <= 1.0
        if row["method"] == "length_pi":
            assert row["policy_used_morphology"] is False
        if row["method"] in {"rule_pi", "rule_pi_rebite"}:
            assert row["policy_used_morphology"] is True
            assert set(row["morphology"]) == set(FEATURE_KEYS)


# ---------------------------------------------------------------------------
# Review follow-ups (2026-09-17): fairness parity and non-constant metrics
# ---------------------------------------------------------------------------


def test_provenance_is_arm_independent() -> None:
    """Every arm must score provenance on the same basis.

    raw_full previously omitted ``units`` from its adapter output, so
    metrics_from_transformed saw an empty unit list and scored it 0.0 while
    every candidate scored 1.0. Under the locked eta=0.95 that disqualified
    the baseline for a reason unrelated to the arm.
    """
    doc = run_phase1_matrix(n_per_family=1, artifact_path=None)

    # Arm independence holds over every row, controls included: provenance may
    # only depend on the source, never on which arm processed it.
    by_arm: dict[str, set[float]] = {}
    for row in doc["rows"]:
        by_arm.setdefault(str(row["method"]), set()).add(float(row["provenance"]))
    assert by_arm, "no rows"
    raw = by_arm["raw_full"]
    for arm, values in by_arm.items():
        assert values == raw, f"{arm} provenance {values} != raw_full {raw}"

    # On workload sources every arm scores 1.0. Negative controls are excluded
    # here because neg_missing_provenance is *supposed* to score below 1.0 —
    # that case is asserted in tests/test_negative_controls.py.
    workload = {float(r["provenance"]) for r in doc["rows"] if r["case_kind"] != "negative_control"}
    assert workload == {1.0}, f"workload provenance must not be penalised: {workload}"


def test_raw_full_exposes_the_same_unit_graph_as_candidates() -> None:
    packet, _ = attach_morphology(generate_family_instances("clean_local", 1)[0])
    raw = dict(get_baseline("raw_full").run(packet, {"domain": "prose"}))
    rule = dict(get_baseline("rule_pi").run(packet, {"domain": "prose"}))
    assert raw["units"], "raw_full must publish units"
    assert {str(u["unit_id"]) for u in raw["units"]} == set(raw["visible_unit_ids"])
    assert isinstance(rule["units"], list)


def test_no_op_arm_payload_is_byte_identical_to_raw() -> None:
    """A text-preserving sequence must not alter the document's separators.

    Joining unit texts with "\n" made a genuine no-op look transformed and
    sent the candidate arms whitespace the baseline never sent.
    """
    doc = run_phase1_matrix(n_per_family=1, artifact_path=None)
    by_case: dict[str, dict[str, Mapping[str, object]]] = {}
    for row in doc["rows"]:
        by_case.setdefault(str(row["case_id"]), {})[str(row["method"])] = row
    checked = 0
    for case_id, arms in by_case.items():
        raw = arms["raw_full"]
        for method in ("length_pi", "rule_pi", "rule_pi_rebite"):
            row = arms[method]
            r_entries = row.get("recoverable_evidence_ids") or []
            loss = row.get("loss_ledger") or []
            if r_entries or loss:
                continue  # something really was removed
            checked += 1
            assert row["payload_sha256"] == raw["payload_sha256"], (
                f"{case_id}/{method}: nothing was removed (R and loss ledger are "
                "empty) yet the payload differs from raw_full"
            )
            assert row["status"] == "no_op", (case_id, method, row["status"])
    assert checked > 0, "no no-op rows to check"


def test_recall_can_fail_when_evidence_is_lost() -> None:
    """The recall metric must be able to report failure, not just 1.0.

    Every row of the offline matrix scores 1.0/1.0, so the matrix alone shows
    only that detection never fires — not that it works.
    """
    from bite_eval.phase1_matrix import metrics_from_transformed

    units = [
        {
            "unit_id": "u-keep",
            "text": "kept",
            "span": {"start": 0, "end": 4, "unit": "char"},
            "source_uri": "s://x",
            "provenance": {
                "unit_id": "u-keep",
                "source_uri": "s://x",
                "byte_or_token_span": "char:0-4",
            },
        }
    ]
    # Gold unit dropped with no R entry: unrecoverable loss.
    lost = metrics_from_transformed(
        gold_ids=["u-keep", "u-gone"], visible_ids=["u-keep"], units=units, r_entries=[]
    )
    assert lost["evidence_recall_visible"] == 0.5
    assert lost["evidence_recall_recoverable"] == 0.5

    # Same omission, but routed into R: visible drops, recoverable holds.
    recovered = metrics_from_transformed(
        gold_ids=["u-keep", "u-gone"],
        visible_ids=["u-keep"],
        units=units,
        r_entries=[{"unit_id": "u-gone", "recoverable": True}],
    )
    assert recovered["evidence_recall_visible"] == 0.5
    assert recovered["evidence_recall_recoverable"] == 1.0


def test_operator_packet_carries_no_gold_or_family_labels() -> None:
    packet = generate_family_instances("clean_local", 1)[0]
    working = ensure_operator_packet(packet)
    forbidden = [
        k
        for k in working
        if str(k).startswith(("gold_", "oracle_", "eval_"))
        or str(k) in {"family", "texture", "facts_id"}
    ]
    assert forbidden == [], forbidden
    assert working["units"], "scrubbing must not drop the unit graph"


def test_arm_differentiation_is_backed_by_real_removal() -> None:
    """A payload difference must be explained by R or the loss ledger.

    Guards against "differentiation" that is only whitespace.
    """
    doc = run_phase1_matrix(n_per_family=1, artifact_path=None)
    by_case: dict[str, dict[str, Mapping[str, object]]] = {}
    for row in doc["rows"]:
        by_case.setdefault(str(row["case_id"]), {})[str(row["method"])] = row
    differing = 0
    for arms in by_case.values():
        raw = arms["raw_full"]
        for method in ("length_pi", "rule_pi", "rule_pi_rebite"):
            row = arms[method]
            if row["payload_sha256"] == raw["payload_sha256"]:
                continue
            differing += 1
            assert row.get("recoverable_evidence_ids") or row.get("loss_ledger"), (
                f"{row['case_id']}/{method}: payload differs from raw_full but "
                "nothing is recorded in R or the loss ledger"
            )
    assert differing > 0, "no arm transformed anything"
