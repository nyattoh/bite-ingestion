#!/usr/bin/env python3
"""Schema-validate run manifests; check ledger sums; reject secret-looking keys."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

_SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|secret|password|passwd|authorization|bearer|private[_-]?key|aws_secret)",
    re.IGNORECASE,
)


def _load_schema(root: Path) -> dict:
    for candidate in (
        root / "spec" / "run-manifest.schema.json",
        root / "schemas" / "run-manifest.schema.json",
    ):
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8"))
    raise FileNotFoundError("run-manifest.schema.json not found under spec/ or schemas/")


def _validate_struct(manifest: dict, schema: dict) -> list[str]:
    """Minimal structural validator (jsonschema optional)."""
    errors: list[str] = []
    try:
        import jsonschema  # type: ignore

        jsonschema.validate(manifest, schema)
        return errors
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001
        return [f"jsonschema: {exc}"]

    required = schema.get("required", [])
    for key in required:
        if key not in manifest:
            errors.append(f"missing required field: {key}")
    if manifest.get("schema") != "bite-run-manifest/v0.1":
        errors.append(f"bad schema id: {manifest.get('schema')!r}")
    if manifest.get("paid_api") is not False:
        errors.append("paid_api must be false")
    metrics = manifest.get("metrics")
    if not isinstance(metrics, dict):
        errors.append("metrics must be object")
    else:
        for k in (
            "quality",
            "evidence_recall_visible",
            "evidence_recall_recoverable",
            "provenance",
            "latency",
        ):
            if k not in metrics:
                errors.append(f"metrics missing {k}")
    buckets = manifest.get("token_buckets")
    if not isinstance(buckets, dict):
        errors.append("token_buckets must be object")
    return errors


def _check_ledger_sums(manifest: dict) -> list[str]:
    errors: list[str] = []
    totals = manifest.get("token_totals")
    buckets = manifest.get("token_buckets")
    if not isinstance(totals, dict):
        totals = {}
        if manifest.get("token_totals") is not None:
            errors.append("token_totals must be object")
    if not isinstance(buckets, dict):
        buckets = {}
        errors.append("token_buckets must be object")
    t_total = manifest.get("T_total")
    if t_total is None:
        errors.append("T_total missing")
        return errors
    # Prefer formula with sum_calls
    t_prof = int(totals.get("T_profiler", buckets.get("T_profiler", 0)) or 0)
    t_rout = int(totals.get("T_router", buckets.get("T_router", 0)) or 0)
    if "sum_calls_in_out" in totals or "sum_calls_in_out" in buckets:
        sum_calls = int(totals.get("sum_calls_in_out", buckets.get("sum_calls_in_out", 0)) or 0)
        expected = t_prof + t_rout + sum_calls
    else:
        expected = (
            t_prof
            + t_rout
            + int(buckets.get("T_target_in", 0) or 0)
            + int(buckets.get("T_target_out", 0) or 0)
            + int(buckets.get("T_rebite", 0) or 0)
            + int(buckets.get("T_baseline", 0) or 0)
            + int(buckets.get("T_calls_other", 0) or 0)
        )
    if int(t_total) != expected:
        errors.append(f"T_total={t_total} != expected={expected}")
    # Recompute from rows if present
    rows = manifest.get("ledger_rows")
    if isinstance(rows, list):
        row_sum = sum(
            int(r.get("tokens_in", 0) or 0) + int(r.get("tokens_out", 0) or 0)
            for r in rows
            if isinstance(r, dict)
        )
        if row_sum != int(t_total):
            errors.append(f"row_sum={row_sum} != T_total={t_total}")
    return errors


def _scan_secrets(obj: object, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = str(k)
            if _SECRET_KEY_RE.search(key) and v not in {"[REDACTED]", "[REDACTED_HASHED]", None}:
                if not (isinstance(v, str) and v.startswith("[REDACTED")):
                    found.append(f"secret-looking key at {path}.{key}")
            found.extend(_scan_secrets(v, f"{path}.{key}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found.extend(_scan_secrets(v, f"{path}[{i}]"))
    return found


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate BITE-13 run manifests")
    ap.add_argument(
        "--root",
        type=Path,
        default=_ROOT,
        help="Repo/dist root containing artifacts/runs",
    )
    ap.add_argument(
        "--runs",
        type=Path,
        default=None,
        help="Override artifacts/runs directory",
    )
    args = ap.parse_args(argv)

    schema = _load_schema(args.root)
    runs_dir = args.runs or (args.root / "artifacts" / "runs")
    failed = 0
    n_checked = 0

    if runs_dir.is_dir():
        manifests = sorted(runs_dir.glob("*/manifest.json"))
        n_checked += len(manifests)
        for path in manifests:
            data = json.loads(path.read_text(encoding="utf-8"))
            errs = []
            errs.extend(_validate_struct(data, schema))
            errs.extend(_check_ledger_sums(data))
            errs.extend(_scan_secrets(data))
            if errs:
                failed += 1
                print(f"FAIL {path}:")
                for e in errs:
                    print(f"  - {e}")
            else:
                print(f"OK   {path} status={data.get('status')} T_total={data.get('T_total')}")
    else:
        print(f"No runs dir: {runs_dir}")

    phase1 = args.root / "artifacts" / "phase1" / "arm_differentiation.json"
    if phase1.is_file():
        n_checked += 1
        data = json.loads(phase1.read_text(encoding="utf-8"))
        from bite_eval.phase1_matrix import validate_matrix_doc

        errs = list(validate_matrix_doc(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase1-offline-matrix.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase1 jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase1}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase1} rows={data.get('n_rows')}")

    phase1d = args.root / "artifacts" / "phase1d" / "confirmatory-offline.json"
    if phase1d.is_file():
        n_checked += 1
        data = json.loads(phase1d.read_text(encoding="utf-8"))
        from bite_eval.phase1d_confirmatory import validate_confirmatory_doc

        errs = list(validate_confirmatory_doc(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase1d-confirmatory-offline.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase1d jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase1d}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase1d} verdict={data.get('verdict')} rows={data.get('confirmatory', {}).get('n_rows')}")

    phase2b = args.root / "artifacts" / "phase2b" / "calibration-token-matrix.json"
    if phase2b.is_file():
        n_checked += 1
        data = json.loads(phase2b.read_text(encoding="utf-8"))
        from bite_bench.phase2b import validate_phase2b_doc

        errs = list(validate_phase2b_doc(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase2b-length-control.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase2b jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase2b}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase2b} verdict={data.get('verdict')} surfaces={data.get('n_surfaces')}")

    phase2c = args.root / "benchmarks" / "spec" / "phase2c-dispersion-freeze.json"
    if phase2c.is_file():
        n_checked += 1
        data = json.loads(phase2c.read_text(encoding="utf-8"))
        from bite_bench.phase2c import validate_freeze_doc

        errs = list(validate_freeze_doc(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase2c-dispersion-freeze.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase2c jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase2c}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(
                f"OK   {phase2c} status={data.get('status')} "
                f"pairs={data.get('n_planned_pairs')}"
            )

    phase2c_v2 = args.root / "benchmarks" / "spec" / "phase2c-dispersion-freeze-v0.2.json"
    if phase2c_v2.is_file():
        n_checked += 1
        data = json.loads(phase2c_v2.read_text(encoding="utf-8"))
        from bite_bench.phase2c import validate_freeze_doc

        errs = list(validate_freeze_doc(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase2c-dispersion-freeze-v0.2.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase2c v0.2 jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase2c_v2}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(
                f"OK   {phase2c_v2} status={data.get('status')} "
                f"pairs={data.get('n_planned_pairs')} supersedes={data.get('supersedes')}"
            )

    phase2d = args.root / "artifacts" / "phase2d" / "confirmatory-offline.json"
    if phase2d.is_file():
        n_checked += 1
        data = json.loads(phase2d.read_text(encoding="utf-8"))
        from bite_eval.phase2d_confirmatory import validate_phase2d_doc

        errs = list(validate_phase2d_doc(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase2d-confirmatory-offline.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase2d jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase2d}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(
                f"OK   {phase2d} verdict={data.get('verdict')} "
                f"n_signal={data.get('n_signal')} n_eligible={data.get('n_eligible')}"
            )

    phase3a = args.root / "artifacts" / "phase3a" / "profiler-mechanism-audit.json"
    if phase3a.is_file():
        n_checked += 1
        data = json.loads(phase3a.read_text(encoding="utf-8"))
        from bite_eval.phase3a_audit import validate_phase3a_doc

        errs = list(validate_phase3a_doc(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3a-profiler-mechanism-audit.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3a jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3a}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(
                f"OK   {phase3a} verdict={data.get('verdict')} "
                f"identical={data.get('n_profiler_vectors_identical')}/"
                f"{data.get('n_pairs')}"
            )

    phase3b = args.root / "artifacts" / "phase3b" / "sensor-evaluation.json"
    if phase3b.is_file():
        n_checked += 1
        data = json.loads(phase3b.read_text(encoding="utf-8"))
        from bite_eval.phase3b_sensor import validate_phase3b_doc

        errs = list(validate_phase3b_doc(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3b-sensor-evaluation.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3b jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3b}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3b} verdict={data.get('verdict')}")

    phase3c = args.root / "artifacts" / "phase3c" / "sensor-generalization.json"
    if phase3c.is_file():
        n_checked += 1
        data = json.loads(phase3c.read_text(encoding="utf-8"))
        from bite_eval.phase3c_audit import validate_phase3c_doc

        errs = list(validate_phase3c_doc(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3c-sensor-generalization.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3c jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3c}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3c} verdict={data.get('verdict')}")

    phase3d = args.root / "benchmarks" / "spec" / "phase3d-sensor-v1-design-freeze.json"
    if phase3d.is_file():
        n_checked += 1
        data = json.loads(phase3d.read_text(encoding="utf-8"))
        from bite_eval.phase3d_v1_freeze import validate_phase3d_doc

        errs = list(validate_phase3d_doc(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3d-sensor-v1-design-freeze.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3d jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3d}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3d} verdict={data.get('verdict')}")

    phase3e = args.root / "artifacts" / "phase3e" / "sensor-v1-validation.json"
    if phase3e.is_file():
        n_checked += 1
        data = json.loads(phase3e.read_text(encoding="utf-8"))
        from bite_eval.phase3e_validate import validate_phase3e_doc

        errs = list(validate_phase3e_doc(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3e-sensor-v1-validation.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3e jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3e}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3e} verdict={data.get('verdict')}")

    if n_checked == 0:
        print("No artifacts to validate", file=sys.stderr)
        return 1
    print(f"Validated {n_checked} artifacts; failures={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
