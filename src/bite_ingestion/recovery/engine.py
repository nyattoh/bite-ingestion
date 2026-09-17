"""RecoverEngine — bounded re-bite against recovery index R."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping, MutableMapping, Sequence
from typing import Any

from bite_ingestion.recovery.audit import append_audit
from bite_ingestion.recovery.budget import RecoverBudget, estimate_tokens
from bite_ingestion.recovery.dedupe import DedupeIndex, request_fetch_key
from bite_ingestion.recovery.guards import check_access, check_version_freshness
from bite_ingestion.recovery.source_store import SourceRecord, SourceStore
from bite_ingestion.recovery.types import (
    ALLOWED_REQUEST_TYPES,
    OutcomeCode,
    RebiteRequest,
    RecoverResult,
    RecoverState,
    RequestType,
    SufficiencyKind,
    ensure_packet_recovery_fields,
    r_entries,
    recovery_handles,
    visible_unit_ids,
)


def _canonical_json(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _stable_eid(*parts: object, length: int = 12) -> str:
    material = "|".join(_canonical_json(p) if not isinstance(p, str) else p for p in parts)
    return "e_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:length]


class RecoverEngine:
    """Bounded Recover: schema'd requests only; never whole-raw resend."""

    def __init__(
        self,
        budget: RecoverBudget | None = None,
        *,
        refuse_injection_suspect: bool = True,
    ) -> None:
        self.budget = budget or RecoverBudget()
        self.refuse_injection_suspect = refuse_injection_suspect

    def recover(
        self,
        packet: Mapping[str, object],
        request: RebiteRequest | Mapping[str, Any],
        source_store: SourceStore,
        state: RecoverState | None = None,
    ) -> RecoverResult:
        """Execute one bounded recover attempt.

        Deterministic: same packet+request+store+state → same result.
        Every attempt increments ``state.calls`` (success or fail).
        """
        state = state if state is not None else RecoverState()
        out_packet: dict[str, Any] = copy.deepcopy(dict(packet))
        ensure_packet_recovery_fields(out_packet)
        req = request if isinstance(request, RebiteRequest) else RebiteRequest.from_mapping(request)

        # --- budget: calls (check before work; still count this attempt) ---
        if self.budget.would_exceed_calls(state.calls):
            state.calls += 1
            return self._finish(
                out_packet,
                state,
                req,
                OutcomeCode.BUDGET_EXHAUSTED.value,
                message="max calls J exhausted (TBD_CALIBRATE)",
            )

        state.calls += 1

        # --- invalid request type ---
        if req.request_type not in ALLOWED_REQUEST_TYPES:
            return self._finish(
                out_packet,
                state,
                req,
                OutcomeCode.INVALID_REQUEST.value,
                message=f"request_type not in Q_req: {req.request_type!r}",
            )

        # --- clarify_sufficiency: meta only ---
        if req.request_type == RequestType.CLARIFY_SUFFICIENCY.value:
            return self._clarify(out_packet, state, req)

        # --- resolve R targets ---
        targets = self._resolve_targets(out_packet, req)
        if not targets:
            return self._finish(
                out_packet,
                state,
                req,
                OutcomeCode.RECOVER_MISS.value,
                message="no R entry matched / outside recovery contract",
                recovery_success=0,
            )

        # --- fetch_aggregate_members expands to member unit_ids in R ---
        if req.request_type == RequestType.FETCH_AGGREGATE_MEMBERS.value:
            return self._fetch_aggregate(out_packet, state, req, source_store, targets)

        # For single-target body fetches, process each target in sorted unit_id order
        # but typically one; aggregate path handled above.
        if req.request_type == RequestType.FETCH_BY_VERSION.value:
            return self._fetch_by_version(out_packet, state, req, source_store, targets)

        # fetch_unit / fetch_span / fetch_quarantine — one or more matched entries
        return self._fetch_bodies(out_packet, state, req, source_store, targets)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _finish(
        self,
        packet: dict[str, Any],
        state: RecoverState,
        req: RebiteRequest,
        outcome: str,
        *,
        returned_evidence_ids: Sequence[str] | None = None,
        estimated_tokens: int = 0,
        message: str = "",
        sufficiency_kind: str | None = None,
        meta: dict[str, Any] | None = None,
        recovery_success: int = 0,
        sync_accounting: bool = True,
    ) -> RecoverResult:
        ids = list(returned_evidence_ids or [])
        if sync_accounting and estimated_tokens:
            acc = dict(packet.get("accounting") or {})
            prev = int(acc.get("rebite_tokens") or 0)
            acc["rebite_tokens"] = prev + int(estimated_tokens)
            packet["accounting"] = acc
            # note: rebite tokens belong in T_total (harness)
            acc_note = dict(acc)
            acc_note["rebite_tokens_in_T_total"] = True
            packet["accounting"] = acc_note
            state.rebite_tokens = int(state.rebite_tokens) + int(estimated_tokens)

        append_audit(
            state,
            request=req,
            outcome=outcome,
            returned_evidence_ids=ids,
            estimated_tokens=estimated_tokens,
            message=message,
            sufficiency_kind=sufficiency_kind,
        )
        # ledger step
        reb = dict(packet.get("rebite") or {"steps": []})
        steps = list(reb.get("steps") or [])
        steps.append(
            {
                "outcome": outcome,
                "request_type": req.request_type,
                "returned_evidence_ids": ids,
                "estimated_tokens": estimated_tokens,
                "message": message,
                "calls": state.calls,
            }
        )
        reb["steps"] = steps
        packet["rebite"] = reb

        return RecoverResult(
            outcome=outcome,
            packet=packet,
            state=state,
            returned_evidence_ids=ids,
            estimated_tokens=estimated_tokens,
            sufficiency_kind=sufficiency_kind,
            meta=meta,
            message=message,
            recovery_success=recovery_success,
        )

    def _clarify(
        self, packet: dict[str, Any], state: RecoverState, req: RebiteRequest
    ) -> RecoverResult:
        entries = r_entries(packet)
        visible = visible_unit_ids(packet)
        missing: list[dict[str, Any]] = []
        for e in entries:
            if not e.get("recoverable", True):
                continue
            uid = str(e.get("unit_id", ""))
            if uid and uid not in visible:
                missing.append(
                    {
                        "unit_id": uid,
                        "r_id": e.get("r_id"),
                        "reason": e.get("reason"),
                        "evidence_type": e.get("reason") or "unspecified",
                    }
                )
        missing.sort(key=lambda m: (str(m.get("reason", "")), str(m.get("unit_id", ""))))
        if missing:
            kind = SufficiencyKind.MISSING_EVIDENCE.value
        else:
            # R has nothing left to fetch → model asked clarify without body need
            kind = SufficiencyKind.MODEL_INDECISION.value
        meta = {
            "sufficiency_kind": kind,
            "missing_evidence_types": sorted({str(m["evidence_type"]) for m in missing}),
            "missing_entries": missing,
            "body_fetched": False,
        }
        # no body into visible_evidence
        return self._finish(
            packet,
            state,
            req,
            OutcomeCode.CLARIFY_META.value,
            message="clarify_sufficiency meta only (no body)",
            sufficiency_kind=kind,
            meta=meta,
            recovery_success=0,
        )

    def _resolve_targets(
        self, packet: Mapping[str, Any], req: RebiteRequest
    ) -> list[dict[str, Any]]:
        """Return R entries in contract for this request (sorted by r_id)."""
        entries = r_entries(packet)
        by_rid = {str(e.get("r_id")): e for e in entries if e.get("r_id")}
        allowed_rids: set[str] | None = None

        if req.handle_id:
            handles = recovery_handles(packet)
            hit = next((h for h in handles if str(h.get("handle_id")) == req.handle_id), None)
            if hit is None:
                return []
            allowed_rids = {str(x) for x in (hit.get("r_ids") or [])}

        def _in_handle(e: dict[str, Any]) -> bool:
            if allowed_rids is None:
                return True
            return str(e.get("r_id")) in allowed_rids

        matched: list[dict[str, Any]] = []

        if req.r_id:
            e = by_rid.get(req.r_id)
            if e is None or not _in_handle(e):
                return []
            matched = [e]
        elif req.request_type == RequestType.FETCH_AGGREGATE_MEMBERS.value:
            parent = req.aggregate_parent or req.unit_id
            if not parent:
                return []
            for e in entries:
                if not _in_handle(e):
                    continue
                if str(e.get("aggregate_parent") or "") == str(parent):
                    matched.append(e)
        elif req.request_type == RequestType.FETCH_QUARANTINE.value:
            quarantine_reasons = {
                "quarantined",
                "injection_suspect",
                "malformed",
                "anomaly_candidate",
            }
            for e in entries:
                if not _in_handle(e):
                    continue
                reason = str(e.get("reason") or "")
                extra = e.get("extra") if isinstance(e.get("extra"), Mapping) else {}
                tags = list(extra.get("reason_tags") or []) if isinstance(extra, Mapping) else []
                is_quar = (
                    reason == "quarantined"
                    or reason.startswith("quarantined")
                    or reason in quarantine_reasons
                    or any(t in quarantine_reasons for t in tags)
                )
                if not is_quar:
                    continue
                if req.reason and reason != req.reason and req.reason not in tags:
                    continue
                if req.unit_id and str(e.get("unit_id")) != req.unit_id:
                    continue
                matched.append(e)
        elif req.request_type == RequestType.FETCH_BY_VERSION.value:
            for e in entries:
                if not _in_handle(e):
                    continue
                if req.unit_id and str(e.get("unit_id")) != req.unit_id:
                    continue
                # Include R hits for the unit; version match enforced against store later
                matched.append(e)
        else:
            # fetch_unit / fetch_span
            if not req.unit_id and not req.r_id and not (req.handle_id and allowed_rids):
                return []
            if req.handle_id and allowed_rids is not None and not req.unit_id:
                matched = [by_rid[r] for r in sorted(allowed_rids) if r in by_rid]
            else:
                for e in entries:
                    if req.unit_id and str(e.get("unit_id")) != req.unit_id:
                        continue
                    if not _in_handle(e):
                        continue
                    if not e.get("recoverable", True):
                        continue
                    matched.append(e)

        seen: set[str] = set()
        uniq: list[dict[str, Any]] = []
        for e in matched:
            rid = str(e.get("r_id") or e.get("unit_id") or "")
            if rid in seen:
                continue
            seen.add(rid)
            uniq.append(e)
        uniq.sort(key=lambda e: str(e.get("r_id", "")))
        return uniq

    def _fetch_bodies(
        self,
        packet: dict[str, Any],
        state: RecoverState,
        req: RebiteRequest,
        store: SourceStore,
        targets: list[dict[str, Any]],
    ) -> RecoverResult:
        dedupe = DedupeIndex.from_state_keys(state.seen_fetch_keys)
        returned: list[str] = []
        total_tokens = 0
        last_outcome = OutcomeCode.RECOVER_MISS.value
        messages: list[str] = []

        for entry in targets:
            uid = str(entry.get("unit_id", ""))
            loc = entry.get("locator") if isinstance(entry.get("locator"), Mapping) else {}
            rec = store.get(uid)
            access = check_access(rec, refuse_injection_suspect=self.refuse_injection_suspect)
            if not access.allowed:
                last_outcome = access.outcome or OutcomeCode.RECOVER_MISS.value
                messages.append(access.message)
                # refuse closes this attempt (no partial add for safety-critical)
                return self._finish(
                    packet,
                    state,
                    req,
                    last_outcome,
                    message=access.message,
                    recovery_success=0,
                )

            assert rec is not None
            req_version = req.version
            if req_version is None and isinstance(loc, Mapping):
                # for fetch_unit without explicit version, use locator version for freshness
                pass
            fresh = check_version_freshness(
                rec,
                request_version=req_version if req_version is not None else None,
                request_stale=req.stale,
                locator=loc if isinstance(loc, Mapping) else None,
            )
            # Special case: if request pins a version and store mismatches → fail
            if (
                req.version is not None
                and rec.version is not None
                and str(req.version) != str(rec.version)
            ):
                return self._finish(
                    packet,
                    state,
                    req,
                    OutcomeCode.STALE_OR_BROKEN_LOCATOR.value,
                    message=fresh.message or "version mismatch",
                    recovery_success=0,
                )
            if (
                req.stale is True
                and req.version is not None
                and rec.version is not None
                and str(req.version) != str(rec.version)
            ):
                return self._finish(
                    packet,
                    state,
                    req,
                    OutcomeCode.STALE_OR_BROKEN_LOCATOR.value,
                    message="stale=true with version mismatch",
                    recovery_success=0,
                )
            if not fresh.allowed and req.version is not None:
                return self._finish(
                    packet,
                    state,
                    req,
                    OutcomeCode.STALE_OR_BROKEN_LOCATOR.value,
                    message=fresh.message,
                    recovery_success=0,
                )
            # broken locator span on fetch_span
            if req.request_type == RequestType.FETCH_SPAN.value:
                span = req.span or (loc.get("span") if isinstance(loc, Mapping) else None)
                if not span:
                    return self._finish(
                        packet,
                        state,
                        req,
                        OutcomeCode.STALE_OR_BROKEN_LOCATOR.value,
                        message="fetch_span missing span",
                        recovery_success=0,
                    )
                text = store.slice_text(uid, span)
                if text is None:
                    return self._finish(
                        packet,
                        state,
                        req,
                        OutcomeCode.STALE_OR_BROKEN_LOCATOR.value,
                        message="stale or broken span locator",
                        recovery_success=0,
                    )
            else:
                span = None
                text = rec.text

            key = request_fetch_key(req, resolved_unit_id=uid)
            if req.request_type == RequestType.FETCH_SPAN.value:
                key = request_fetch_key(
                    RebiteRequest(
                        request_type=req.request_type,
                        unit_id=uid,
                        span=req.span or (loc.get("span") if isinstance(loc, Mapping) else None),
                        version=req.version,
                    ),
                    resolved_unit_id=uid,
                )
            if key in dedupe:
                return self._finish(
                    packet,
                    state,
                    req,
                    OutcomeCode.SUPPRESSED_REPEAT.value,
                    message="identical successful fetch suppressed",
                    recovery_success=0,
                )

            tok = estimate_tokens(text)
            if self.budget.would_exceed_tokens(state.rebite_tokens, tok):
                return self._finish(
                    packet,
                    state,
                    req,
                    OutcomeCode.BUDGET_EXHAUSTED.value,
                    message="token ceiling Br exhausted (TBD_CALIBRATE)",
                    recovery_success=0,
                )

            eid = self._add_evidence(
                packet, unit_id=uid, text=text, record=rec, span=span or req.span
            )
            returned.append(eid)
            total_tokens += tok
            dedupe.add(key)
            if key not in state.seen_fetch_keys:
                state.seen_fetch_keys.append(key)
            last_outcome = OutcomeCode.SUCCESS.value
            messages.append("ok")
            self._append_tau_recover(
                packet, inputs_ref=[str(entry.get("r_id", uid))], outputs_ref=[eid]
            )

        if not returned:
            return self._finish(
                packet,
                state,
                req,
                last_outcome
                if last_outcome != OutcomeCode.SUCCESS.value
                else OutcomeCode.RECOVER_MISS.value,
                message="; ".join(messages) or "recover_miss",
                recovery_success=0,
            )

        return self._finish(
            packet,
            state,
            req,
            OutcomeCode.SUCCESS.value,
            returned_evidence_ids=returned,
            estimated_tokens=total_tokens,
            message="recovered",
            recovery_success=1,
        )

    def _fetch_aggregate(
        self,
        packet: dict[str, Any],
        state: RecoverState,
        req: RebiteRequest,
        store: SourceStore,
        targets: list[dict[str, Any]],
    ) -> RecoverResult:
        parent = req.aggregate_parent or req.unit_id
        # Prefer R-matched targets; also allow store members if their unit_ids are in R
        r_uids = {str(e.get("unit_id")) for e in targets}
        members = store.members_of_aggregate(str(parent))
        member_entries: list[dict[str, Any]] = []
        if members:
            entry_by_uid = {str(e.get("unit_id")): e for e in targets}
            for m in members:
                if m.unit_id in r_uids or m.unit_id in entry_by_uid:
                    member_entries.append(
                        entry_by_uid.get(m.unit_id)
                        or {
                            "unit_id": m.unit_id,
                            "r_id": f"r_synth_{m.unit_id}",
                            "locator": {},
                            "recoverable": True,
                        }
                    )
        if not member_entries:
            # targets themselves are the members listed under aggregate_parent in R
            member_entries = targets
        if not member_entries:
            return self._finish(
                packet,
                state,
                req,
                OutcomeCode.RECOVER_MISS.value,
                message="no aggregate members in R",
                recovery_success=0,
            )
        # Reuse body fetch with synthetic unit requests
        syn_req = RebiteRequest(
            request_type=RequestType.FETCH_UNIT.value,
            request_id=req.request_id,
            aggregate_parent=parent,
            notes=req.notes,
        )
        # Dedupe key uses aggregate request type
        key = request_fetch_key(req)
        dedupe = DedupeIndex.from_state_keys(state.seen_fetch_keys)
        if key in dedupe:
            return self._finish(
                packet,
                state,
                req,
                OutcomeCode.SUPPRESSED_REPEAT.value,
                message="identical aggregate fetch suppressed",
                recovery_success=0,
            )

        returned: list[str] = []
        total_tokens = 0
        for entry in sorted(member_entries, key=lambda e: str(e.get("unit_id", ""))):
            uid = str(entry.get("unit_id", ""))
            rec = store.get(uid)
            access = check_access(rec, refuse_injection_suspect=self.refuse_injection_suspect)
            if not access.allowed:
                return self._finish(
                    packet,
                    state,
                    req,
                    access.outcome or OutcomeCode.RECOVER_MISS.value,
                    message=access.message,
                    recovery_success=0,
                )
            assert rec is not None
            tok = estimate_tokens(rec.text)
            if self.budget.would_exceed_tokens(state.rebite_tokens + total_tokens, tok):
                return self._finish(
                    packet,
                    state,
                    req,
                    OutcomeCode.BUDGET_EXHAUSTED.value,
                    message="token ceiling Br exhausted (TBD_CALIBRATE)",
                    recovery_success=0,
                )
            eid = self._add_evidence(packet, unit_id=uid, text=rec.text, record=rec, span=None)
            returned.append(eid)
            total_tokens += tok
            self._append_tau_recover(
                packet, inputs_ref=[str(entry.get("r_id", uid))], outputs_ref=[eid]
            )

        if returned:
            dedupe.add(key)
            if key not in state.seen_fetch_keys:
                state.seen_fetch_keys.append(key)

        # mark syn_req unused
        _ = syn_req

        if not returned:
            return self._finish(
                packet,
                state,
                req,
                OutcomeCode.RECOVER_MISS.value,
                message="aggregate members empty after guards",
                recovery_success=0,
            )
        return self._finish(
            packet,
            state,
            req,
            OutcomeCode.SUCCESS.value,
            returned_evidence_ids=returned,
            estimated_tokens=total_tokens,
            message="aggregate members recovered",
            recovery_success=1,
        )

    def _fetch_by_version(
        self,
        packet: dict[str, Any],
        state: RecoverState,
        req: RebiteRequest,
        store: SourceStore,
        targets: list[dict[str, Any]],
    ) -> RecoverResult:
        if req.version is None:
            return self._finish(
                packet,
                state,
                req,
                OutcomeCode.INVALID_REQUEST.value,
                message="fetch_by_version requires version",
                recovery_success=0,
            )
        # Filter targets whose locator.version matches OR resolve via store
        matched: list[dict[str, Any]] = []
        for e in targets:
            loc = e.get("locator") if isinstance(e.get("locator"), Mapping) else {}
            ver = loc.get("version") if isinstance(loc, Mapping) else None
            uid = str(e.get("unit_id", ""))
            rec = store.get(uid)
            if (
                rec is not None
                and str(rec.version) == str(req.version)
                or ver is not None
                and str(ver) == str(req.version)
            ):
                matched.append(e)
        if not matched:
            # version mismatch on requested unit → stale path if unit in R
            if targets:
                return self._finish(
                    packet,
                    state,
                    req,
                    OutcomeCode.STALE_OR_BROKEN_LOCATOR.value,
                    message="requested version not available for R targets",
                    recovery_success=0,
                )
            return self._finish(
                packet,
                state,
                req,
                OutcomeCode.RECOVER_MISS.value,
                message="no R entry for version",
                recovery_success=0,
            )
        # Force version on request for freshness
        pinned = RebiteRequest(
            request_type=RequestType.FETCH_UNIT.value,
            request_id=req.request_id,
            unit_id=req.unit_id,
            version=req.version,
            stale=req.stale,
            notes=req.notes,
        )
        # Use body fetch but keep original req for audit — wrap manually
        result = self._fetch_bodies(packet, state, pinned, store, matched)
        # Rewrite audit last entry request_type back? Keep pinned for body semantics.
        # Prefer original request in a patched finish: adjust outcome packet already set.
        if result.outcome == OutcomeCode.SUCCESS.value:
            # fix last rebite step request_type display
            reb = dict(result.packet.get("rebite") or {})
            steps = list(reb.get("steps") or [])
            if steps:
                steps[-1]["request_type"] = RequestType.FETCH_BY_VERSION.value
                reb["steps"] = steps
                result.packet["rebite"] = reb
        return result

    def _add_evidence(
        self,
        packet: MutableMapping[str, Any],
        *,
        unit_id: str,
        text: str,
        record: SourceRecord,
        span: Mapping[str, Any] | None,
    ) -> str:
        eid = _stable_eid(unit_id, text, span or {})
        item: dict[str, Any] = {
            "e_id": eid,
            "text": text,
            "role": "recovered",
            "unit_ids": [unit_id],
            "provenance": {
                "unit_id": unit_id,
                "source_uri": record.uri,
                "version": record.version,
                "span": dict(span) if span else (dict(record.span) if record.span else None),
                "op_last_touch": "RECOVER",
            },
        }
        visible = list(packet.get("visible_evidence") or [])
        # suppress exact e_id duplicates
        if not any(isinstance(v, Mapping) and v.get("e_id") == eid for v in visible):
            visible.append(item)
        packet["visible_evidence"] = visible

        units = list(packet.get("units") or [])
        if not any(isinstance(u, Mapping) and u.get("unit_id") == unit_id for u in units):
            span_d = (
                dict(span)
                if span
                else (
                    dict(record.span)
                    if record.span
                    else {"start": 0, "end": len(text), "unit": "char"}
                )
            )
            units.append(
                {
                    "unit_id": unit_id,
                    "text": text,
                    "span": span_d,
                    "source_uri": record.uri,
                    "version": record.version,
                    "media_type": record.media_type,
                    "parent_unit_id": unit_id,
                    "provenance": {
                        "unit_id": unit_id,
                        "source_uri": record.uri,
                        "byte_or_token_span": (f"char:{span_d.get('start')}-{span_d.get('end')}"),
                        "renderer_id": "recover",
                    },
                }
            )
            units.sort(key=lambda u: str(u.get("unit_id", "")) if isinstance(u, Mapping) else "")
        packet["units"] = units
        packet["op_last_touch"] = "RECOVER"

        # keep top-level provenance pointing at last recovered unit (non-destructive merge)
        prov = dict(packet.get("provenance") or {})
        prov.setdefault("unit_id", unit_id)
        if record.uri:
            prov["source_uri"] = record.uri
        packet["provenance"] = prov
        return eid

    def _append_tau_recover(
        self,
        packet: MutableMapping[str, Any],
        *,
        inputs_ref: Sequence[str],
        outputs_ref: Sequence[str],
    ) -> None:
        tau = dict(packet.get("tau") or {"sequence": [], "steps": []})
        seq = list(tau.get("sequence") or [])
        seq.append("RECOVER")
        tau["sequence"] = seq
        steps = list(tau.get("steps") or [])
        steps.append(
            {
                "op": "RECOVER",
                "mode": "deterministic",
                "inputs_ref": list(inputs_ref),
                "outputs_ref": list(outputs_ref),
                "omitted_ref": [],
                "errors": [],
                "extra": {},
            }
        )
        tau["steps"] = steps
        packet["tau"] = tau
