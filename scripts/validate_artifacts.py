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

    from bite_bench.phase3f import validate_phase3f_doc

    for phase3f, schema_name in (
        (
            args.root / "benchmarks" / "spec" / "phase3f-routing-calibration-freeze.json",
            "phase3f-routing-calibration-freeze.schema.json",
        ),
        (
            args.root / "benchmarks" / "spec" / "phase3f-routing-calibration-freeze-v0.2.json",
            "phase3f-routing-calibration-freeze-v0.2.schema.json",
        ),
        (
            args.root / "benchmarks" / "spec" / "phase3f-routing-calibration-freeze-v0.3.json",
            "phase3f-routing-calibration-freeze-v0.3.schema.json",
        ),
    ):
        if not phase3f.is_file():
            continue
        n_checked += 1
        data = json.loads(phase3f.read_text(encoding="utf-8"))
        errs = list(validate_phase3f_doc(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / schema_name
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3f jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3f}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(
                f"OK   {phase3f} verdict={data.get('verdict')} revision={data.get('revision')}"
            )

    from bite_eval.phase3g_calibrate import validate_phase3g_lock

    phase3g = args.root / "artifacts" / "phase3g" / "calibration-lock.json"
    if phase3g.is_file():
        n_checked += 1
        data = json.loads(phase3g.read_text(encoding="utf-8"))
        errs = list(validate_phase3g_lock(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3g-calibration-lock.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3g jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3g}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3g} verdict={data.get('verdict')}")

    from bite_bench.phase3h import validate_phase3h_freeze
    from bite_eval.phase3h_experiment import validate_phase3h_experiment

    phase3h_freeze = args.root / "benchmarks" / "spec" / "phase3h-operator-map-freeze.json"
    if phase3h_freeze.is_file():
        n_checked += 1
        data = json.loads(phase3h_freeze.read_text(encoding="utf-8"))
        errs = list(validate_phase3h_freeze(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3h-operator-map-freeze.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3h freeze jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3h_freeze}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3h_freeze} verdict={data.get('verdict')}")

    phase3h = args.root / "artifacts" / "phase3h" / "operator-map-experiment.json"
    if phase3h.is_file():
        n_checked += 1
        data = json.loads(phase3h.read_text(encoding="utf-8"))
        errs = list(validate_phase3h_experiment(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3h-operator-map-experiment.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3h jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3h}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3h} verdict={data.get('verdict')}")

    from bite_bench.phase3i import validate_phase3i_freeze
    from bite_eval.phase3i_validate import validate_phase3i_result

    phase3i_freeze = args.root / "benchmarks" / "spec" / "phase3i-composite-provenance-freeze.json"
    if phase3i_freeze.is_file():
        n_checked += 1
        data = json.loads(phase3i_freeze.read_text(encoding="utf-8"))
        errs = list(validate_phase3i_freeze(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3i-composite-provenance-freeze.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3i freeze jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3i_freeze}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3i_freeze} verdict={data.get('verdict')}")

    phase3i = args.root / "artifacts" / "phase3i" / "composite-provenance.json"
    if phase3i.is_file():
        n_checked += 1
        data = json.loads(phase3i.read_text(encoding="utf-8"))
        errs = list(validate_phase3i_result(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3i-composite-provenance.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3i jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3i}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3i} verdict={data.get('verdict')}")

    from bite_bench.phase3j import validate_phase3j_freeze
    from bite_eval.phase3j_audit import validate_phase3j_result

    phase3j_freeze = args.root / "benchmarks" / "spec" / "phase3j-texture-observability-freeze.json"
    if phase3j_freeze.is_file():
        n_checked += 1
        data = json.loads(phase3j_freeze.read_text(encoding="utf-8"))
        errs = list(validate_phase3j_freeze(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3j-texture-observability-freeze.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3j freeze jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3j_freeze}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3j_freeze} verdict={data.get('verdict')}")

    phase3j = args.root / "artifacts" / "phase3j" / "texture-observability.json"
    if phase3j.is_file():
        n_checked += 1
        data = json.loads(phase3j.read_text(encoding="utf-8"))
        errs = list(validate_phase3j_result(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3j-texture-observability.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3j jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3j}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3j} verdict={data.get('verdict')}")

    from bite_bench.phase3k import validate_phase3k_freeze, validate_phase3k_split
    from bite_eval.phase3k_validate import validate_phase3k_result

    phase3k_freeze = args.root / "benchmarks" / "spec" / "phase3k-structural-redundancy-freeze.json"
    if phase3k_freeze.is_file():
        n_checked += 1
        data = json.loads(phase3k_freeze.read_text(encoding="utf-8"))
        errs = list(validate_phase3k_freeze(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3k-structural-redundancy-freeze.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3k freeze jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3k_freeze}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3k_freeze} verdict={data.get('verdict')}")

    phase3k_split = args.root / "benchmarks" / "spec" / "phase3k-split-manifest.json"
    if phase3k_split.is_file():
        n_checked += 1
        data = json.loads(phase3k_split.read_text(encoding="utf-8"))
        errs = list(validate_phase3k_split(data))
        errs.extend(_scan_secrets(data))
        if errs:
            failed += 1
            print(f"FAIL {phase3k_split}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3k_split} generation={data.get('generation')}")

    phase3k = args.root / "artifacts" / "phase3k" / "structural-redundancy.json"
    if phase3k.is_file():
        n_checked += 1
        data = json.loads(phase3k.read_text(encoding="utf-8"))
        errs = list(validate_phase3k_result(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3k-structural-redundancy.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3k jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3k}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3k} verdict={data.get('verdict')}")

    from bite_bench.phase3l import validate_phase3l_freeze
    from bite_eval.phase3l_eval import validate_phase3l_result

    phase3l_freeze = args.root / "benchmarks" / "spec" / "phase3l-redundancy-first-open-freeze.json"
    if phase3l_freeze.is_file():
        n_checked += 1
        data = json.loads(phase3l_freeze.read_text(encoding="utf-8"))
        errs = list(validate_phase3l_freeze(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3l-redundancy-first-open-freeze.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3l freeze jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3l_freeze}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3l_freeze} verdict={data.get('verdict')}")

    phase3l = args.root / "artifacts" / "phase3l" / "redundancy-first-open.json"
    if phase3l.is_file():
        n_checked += 1
        data = json.loads(phase3l.read_text(encoding="utf-8"))
        errs = list(validate_phase3l_result(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3l-redundancy-first-open.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3l jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3l}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3l} verdict={data.get('verdict')}")

    from bite_bench.phase3m import validate_phase3m_freeze, validate_phase3m_split
    from bite_eval.phase3m_eval import validate_phase3m_result

    phase3m_freeze = args.root / "benchmarks" / "spec" / "phase3m-conditional-routing-freeze.json"
    if phase3m_freeze.is_file():
        n_checked += 1
        data = json.loads(phase3m_freeze.read_text(encoding="utf-8"))
        errs = list(validate_phase3m_freeze(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3m-conditional-routing-freeze.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3m freeze jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3m_freeze}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3m_freeze} verdict={data.get('verdict')}")

    phase3m_split = args.root / "benchmarks" / "spec" / "phase3m-split-manifest.json"
    if phase3m_split.is_file():
        n_checked += 1
        data = json.loads(phase3m_split.read_text(encoding="utf-8"))
        errs = list(validate_phase3m_split(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3m-split-manifest.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3m split jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3m_split}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3m_split} generation={data.get('generation')}")

    phase3m = args.root / "artifacts" / "phase3m" / "conditional-routing.json"
    if phase3m.is_file():
        n_checked += 1
        data = json.loads(phase3m.read_text(encoding="utf-8"))
        errs = list(validate_phase3m_result(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3m-conditional-routing.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3m jsonschema: {exc}")
        safety = args.root / "artifacts" / "phase3m" / "composition-safety.json"
        if safety.is_file():
            safety_doc = json.loads(safety.read_text(encoding="utf-8"))
            safety_schema = args.root / "spec" / "phase3m-composition-safety.schema.json"
            if safety_schema.is_file():
                try:
                    import jsonschema  # type: ignore

                    jsonschema.validate(
                        safety_doc, json.loads(safety_schema.read_text(encoding="utf-8"))
                    )
                except ImportError:
                    pass
                except Exception as exc:  # noqa: BLE001
                    errs.append(f"phase3m safety jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3m}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3m} verdict={data.get('verdict')}")

    from bite_bench.phase3n import validate_phase3n_freeze
    from bite_eval.phase3n_eval import validate_phase3n_result

    phase3n_freeze = (
        args.root / "benchmarks" / "spec" / "phase3n-conditional-routing-first-open-freeze.json"
    )
    if phase3n_freeze.is_file():
        n_checked += 1
        data = json.loads(phase3n_freeze.read_text(encoding="utf-8"))
        errs = list(validate_phase3n_freeze(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3n-conditional-routing-first-open-freeze.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3n freeze jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3n_freeze}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3n_freeze} verdict={data.get('verdict')}")

    phase3n = args.root / "artifacts" / "phase3n" / "conditional-routing-first-open.json"
    if phase3n.is_file():
        n_checked += 1
        data = json.loads(phase3n.read_text(encoding="utf-8"))
        errs = list(validate_phase3n_result(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3n-conditional-routing-first-open.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3n jsonschema: {exc}")
        for extra, extra_schema in (
            (
                args.root / "artifacts" / "phase3n" / "routing-comparison.json",
                args.root / "spec" / "phase3n-routing-comparison.schema.json",
            ),
            (
                args.root / "artifacts" / "phase3n" / "composition-safety.json",
                args.root / "spec" / "phase3n-composition-safety.schema.json",
            ),
        ):
            if extra.is_file() and extra_schema.is_file():
                extra_doc = json.loads(extra.read_text(encoding="utf-8"))
                try:
                    import jsonschema  # type: ignore

                    jsonschema.validate(
                        extra_doc, json.loads(extra_schema.read_text(encoding="utf-8"))
                    )
                except ImportError:
                    pass
                except Exception as exc:  # noqa: BLE001
                    errs.append(f"phase3n extra jsonschema {extra.name}: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3n}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3n} verdict={data.get('verdict')}")

    from bite_bench.phase3o import validate_phase3o_freeze
    from bite_eval.phase3o_eval import validate_phase3o_result

    phase3o_freeze = args.root / "benchmarks" / "spec" / "phase3o-xfer1-freeze.json"
    if phase3o_freeze.is_file():
        n_checked += 1
        data = json.loads(phase3o_freeze.read_text(encoding="utf-8"))
        errs = list(validate_phase3o_freeze(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3o-xfer1-freeze.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3o freeze jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3o_freeze}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3o_freeze} verdict={data.get('verdict')}")

    phase3o = args.root / "artifacts" / "phase3o" / "xfer1-transfer.json"
    if phase3o.is_file():
        n_checked += 1
        data = json.loads(phase3o.read_text(encoding="utf-8"))
        errs = list(validate_phase3o_result(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3o-xfer1-transfer.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3o jsonschema: {exc}")
        for extra, extra_schema in (
            (
                args.root / "artifacts" / "phase3o" / "cross-format.json",
                args.root / "spec" / "phase3o-cross-format.schema.json",
            ),
            (
                args.root / "artifacts" / "phase3o" / "actionability.json",
                args.root / "spec" / "phase3o-actionability.schema.json",
            ),
            (
                args.root / "artifacts" / "phase3o" / "composition-safety.json",
                args.root / "spec" / "phase3o-composition-safety.schema.json",
            ),
            (
                args.root / "artifacts" / "phase3o" / "failure-classification.json",
                args.root / "spec" / "phase3o-failure-classification.schema.json",
            ),
        ):
            if extra.is_file() and extra_schema.is_file():
                extra_doc = json.loads(extra.read_text(encoding="utf-8"))
                try:
                    import jsonschema  # type: ignore

                    jsonschema.validate(
                        extra_doc, json.loads(extra_schema.read_text(encoding="utf-8"))
                    )
                except ImportError:
                    pass
                except Exception as exc:  # noqa: BLE001
                    errs.append(f"phase3o extra jsonschema {extra.name}: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3o}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3o} verdict={data.get('verdict')}")

    from bite_bench.phase3p import validate_phase3p_freeze
    from bite_eval.phase3p_eval import validate_phase3p_result

    phase3p_freeze = args.root / "benchmarks" / "spec" / "phase3p-record-alignment-freeze.json"
    if phase3p_freeze.is_file():
        n_checked += 1
        data = json.loads(phase3p_freeze.read_text(encoding="utf-8"))
        errs = list(validate_phase3p_freeze(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3p-record-alignment-freeze.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3p freeze jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3p_freeze}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3p_freeze} verdict={data.get('verdict')}")

    phase3p = args.root / "artifacts" / "phase3p" / "record-alignment.json"
    if phase3p.is_file():
        n_checked += 1
        data = json.loads(phase3p.read_text(encoding="utf-8"))
        errs = list(validate_phase3p_result(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3p-record-alignment.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3p jsonschema: {exc}")
        for extra, extra_schema in (
            (
                args.root / "artifacts" / "phase3p" / "sensor-operator-alignment.json",
                args.root / "spec" / "phase3p-sensor-operator-alignment.schema.json",
            ),
            (
                args.root / "artifacts" / "phase3p" / "lineage-safety.json",
                args.root / "spec" / "phase3p-lineage-safety.schema.json",
            ),
            (
                args.root / "artifacts" / "phase3p" / "xfer1-reproduction.json",
                args.root / "spec" / "phase3p-xfer1-reproduction.schema.json",
            ),
        ):
            if extra.is_file() and extra_schema.is_file():
                extra_doc = json.loads(extra.read_text(encoding="utf-8"))
                try:
                    import jsonschema  # type: ignore

                    jsonschema.validate(
                        extra_doc, json.loads(extra_schema.read_text(encoding="utf-8"))
                    )
                except ImportError:
                    pass
                except Exception as exc:  # noqa: BLE001
                    errs.append(f"phase3p extra jsonschema {extra.name}: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3p}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3p} verdict={data.get('verdict')}")

    from bite_bench.phase3q import validate_phase3q_freeze
    from bite_eval.phase3q_eval import validate_phase3q_result

    phase3q_freeze = args.root / "benchmarks" / "spec" / "phase3q-xfer2-freeze.json"
    if phase3q_freeze.is_file():
        n_checked += 1
        data = json.loads(phase3q_freeze.read_text(encoding="utf-8"))
        errs = list(validate_phase3q_freeze(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3q-xfer2-freeze.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3q freeze jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3q_freeze}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3q_freeze} verdict={data.get('verdict')}")

    phase3q = args.root / "artifacts" / "phase3q" / "xfer2-transfer.json"
    if phase3q.is_file():
        n_checked += 1
        data = json.loads(phase3q.read_text(encoding="utf-8"))
        errs = list(validate_phase3q_result(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3q-xfer2-transfer.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3q jsonschema: {exc}")
        for extra, extra_schema in (
            (
                args.root / "artifacts" / "phase3q" / "cross-format.json",
                args.root / "spec" / "phase3q-cross-format.schema.json",
            ),
            (
                args.root / "artifacts" / "phase3q" / "actionability.json",
                args.root / "spec" / "phase3q-actionability.schema.json",
            ),
            (
                args.root / "artifacts" / "phase3q" / "composition-safety.json",
                args.root / "spec" / "phase3q-composition-safety.schema.json",
            ),
            (
                args.root / "artifacts" / "phase3q" / "operator-interference.json",
                args.root / "spec" / "phase3q-operator-interference.schema.json",
            ),
            (
                args.root / "artifacts" / "phase3q" / "failure-classification.json",
                args.root / "spec" / "phase3q-failure-classification.schema.json",
            ),
        ):
            if extra.is_file() and extra_schema.is_file():
                extra_doc = json.loads(extra.read_text(encoding="utf-8"))
                try:
                    import jsonschema  # type: ignore

                    jsonschema.validate(
                        extra_doc, json.loads(extra_schema.read_text(encoding="utf-8"))
                    )
                except ImportError:
                    pass
                except Exception as exc:  # noqa: BLE001
                    errs.append(f"phase3q extra jsonschema {extra.name}: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3q}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3q} verdict={data.get('verdict')}")

    from bite_bench.phase3r import validate_phase3r_freeze
    from bite_eval.phase3r_eval import validate_phase3r_result

    phase3r_freeze = args.root / "benchmarks" / "spec" / "phase3r-channel-planner-freeze.json"
    if phase3r_freeze.is_file():
        n_checked += 1
        data = json.loads(phase3r_freeze.read_text(encoding="utf-8"))
        errs = list(validate_phase3r_freeze(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3r-channel-planner-freeze.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3r freeze jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3r_freeze}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3r_freeze} verdict={data.get('verdict')}")

    phase3r = args.root / "artifacts" / "phase3r" / "channel-planner.json"
    if phase3r.is_file():
        n_checked += 1
        data = json.loads(phase3r.read_text(encoding="utf-8"))
        errs = list(validate_phase3r_result(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3r-channel-planner.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3r jsonschema: {exc}")
        for extra, extra_schema in (
            (
                args.root / "artifacts" / "phase3r" / "channel-separation.json",
                args.root / "spec" / "phase3r-channel-separation.schema.json",
            ),
            (
                args.root / "artifacts" / "phase3r" / "planner-integrity.json",
                args.root / "spec" / "phase3r-planner-integrity.schema.json",
            ),
            (
                args.root / "artifacts" / "phase3r" / "composition-safety.json",
                args.root / "spec" / "phase3r-composition-safety.schema.json",
            ),
            (
                args.root / "artifacts" / "phase3r" / "xfer2-regression.json",
                args.root / "spec" / "phase3r-xfer2-regression.schema.json",
            ),
        ):
            if extra.is_file() and extra_schema.is_file():
                extra_doc = json.loads(extra.read_text(encoding="utf-8"))
                try:
                    import jsonschema  # type: ignore

                    jsonschema.validate(
                        extra_doc, json.loads(extra_schema.read_text(encoding="utf-8"))
                    )
                except ImportError:
                    pass
                except Exception as exc:  # noqa: BLE001
                    errs.append(f"phase3r extra jsonschema {extra.name}: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3r}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3r} verdict={data.get('verdict')}")

    from bite_bench.phase3s import validate_phase3s_freeze
    from bite_eval.phase3s_eval import validate_phase3s_result

    phase3s_freeze = args.root / "benchmarks" / "spec" / "phase3s-reference-specificity-freeze.json"
    if phase3s_freeze.is_file():
        n_checked += 1
        data = json.loads(phase3s_freeze.read_text(encoding="utf-8"))
        errs = list(validate_phase3s_freeze(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3s-reference-specificity-freeze.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3s freeze jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3s_freeze}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3s_freeze} verdict={data.get('verdict')}")

    phase3s = args.root / "artifacts" / "phase3s" / "reference-specificity.json"
    if phase3s.is_file():
        n_checked += 1
        data = json.loads(phase3s.read_text(encoding="utf-8"))
        errs = list(validate_phase3s_result(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3s-reference-specificity.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3s jsonschema: {exc}")
        for extra, extra_schema in (
            (
                args.root / "artifacts" / "phase3s" / "edge-rows.json",
                args.root / "spec" / "phase3s-edge-rows.schema.json",
            ),
            (
                args.root / "artifacts" / "phase3s" / "edge-precision.json",
                args.root / "spec" / "phase3s-edge-precision.schema.json",
            ),
            (
                args.root / "artifacts" / "phase3s" / "gate.json",
                args.root / "spec" / "phase3s-gate.schema.json",
            ),
            (
                args.root / "artifacts" / "phase3s" / "policy-consequence.json",
                args.root / "spec" / "phase3s-policy-consequence.schema.json",
            ),
            (
                args.root / "artifacts" / "phase3s" / "cross-format.json",
                args.root / "spec" / "phase3s-cross-format.schema.json",
            ),
        ):
            if extra.is_file() and extra_schema.is_file():
                extra_doc = json.loads(extra.read_text(encoding="utf-8"))
                try:
                    import jsonschema  # type: ignore

                    jsonschema.validate(
                        extra_doc, json.loads(extra_schema.read_text(encoding="utf-8"))
                    )
                except ImportError:
                    pass
                except Exception as exc:  # noqa: BLE001
                    errs.append(f"phase3s extra jsonschema {extra.name}: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3s}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3s} verdict={data.get('verdict')}")

    from bite_bench.phase3t import validate_phase3t_freeze
    from bite_eval.phase3t_eval import validate_phase3t_result

    phase3t_freeze = args.root / "benchmarks" / "spec" / "phase3t-exact-reference-freeze.json"
    if phase3t_freeze.is_file():
        n_checked += 1
        data = json.loads(phase3t_freeze.read_text(encoding="utf-8"))
        errs = list(validate_phase3t_freeze(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3t-exact-reference-freeze.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3t freeze jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3t_freeze}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3t_freeze} verdict={data.get('verdict')}")

    phase3t = args.root / "artifacts" / "phase3t" / "exact-reference.json"
    if phase3t.is_file():
        n_checked += 1
        data = json.loads(phase3t.read_text(encoding="utf-8"))
        errs = list(validate_phase3t_result(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase3t-exact-reference.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase3t jsonschema: {exc}")
        for extra, extra_schema in (
            (
                args.root / "artifacts" / "phase3t" / "exact-edge.json",
                args.root / "spec" / "phase3t-exact-edge.schema.json",
            ),
            (
                args.root / "artifacts" / "phase3t" / "threshold-bridge.json",
                args.root / "spec" / "phase3t-threshold-bridge.schema.json",
            ),
            (
                args.root / "artifacts" / "phase3t" / "gate.json",
                args.root / "spec" / "phase3t-gate.schema.json",
            ),
            (
                args.root / "artifacts" / "phase3t" / "policy-consequence.json",
                args.root / "spec" / "phase3t-policy-consequence.schema.json",
            ),
            (
                args.root / "artifacts" / "phase3t" / "phase3s-regression.json",
                args.root / "spec" / "phase3t-phase3s-regression.schema.json",
            ),
        ):
            if extra.is_file() and extra_schema.is_file():
                extra_doc = json.loads(extra.read_text(encoding="utf-8"))
                try:
                    import jsonschema  # type: ignore

                    jsonschema.validate(
                        extra_doc, json.loads(extra_schema.read_text(encoding="utf-8"))
                    )
                except ImportError:
                    pass
                except Exception as exc:  # noqa: BLE001
                    errs.append(f"phase3t extra jsonschema {extra.name}: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase3t}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase3t} verdict={data.get('verdict')}")

    from bite_bench.phase4a import validate_phase4a_freeze
    from bite_bench.realstruct1 import validate_phase4a_corpus

    phase4a_freeze = args.root / "benchmarks" / "spec" / "phase4a-realstruct1-freeze.json"
    if phase4a_freeze.is_file():
        n_checked += 1
        data = json.loads(phase4a_freeze.read_text(encoding="utf-8"))
        errs = list(validate_phase4a_freeze(data))
        schema_path = args.root / "spec" / "phase4a-realstruct1-freeze.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase4a freeze jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase4a_freeze}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase4a_freeze} verdict={data.get('verdict')}")

    phase4a = args.root / "artifacts" / "phase4a" / "realstruct-1.json"
    if phase4a.is_file():
        n_checked += 1
        data = json.loads(phase4a.read_text(encoding="utf-8"))
        errs = list(validate_phase4a_corpus(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase4a-realstruct1.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase4a jsonschema: {exc}")
        for extra, extra_schema in (
            (
                args.root / "corpora" / "realstruct-1" / "manifest.json",
                args.root / "spec" / "phase4a-realstruct1-corpus.schema.json",
            ),
            (
                args.root / "corpora" / "realstruct-1" / "licenses.json",
                args.root / "spec" / "phase4a-realstruct1-licenses.schema.json",
            ),
            (
                args.root / "corpora" / "realstruct-1" / "split.json",
                args.root / "spec" / "phase4a-realstruct1-split.schema.json",
            ),
            (
                args.root / "corpora" / "realstruct-1" / "annotations.json",
                args.root / "spec" / "phase4a-realstruct1-annotations.schema.json",
            ),
        ):
            if extra.is_file() and extra_schema.is_file():
                extra_doc = json.loads(extra.read_text(encoding="utf-8"))
                try:
                    import jsonschema  # type: ignore

                    jsonschema.validate(
                        extra_doc, json.loads(extra_schema.read_text(encoding="utf-8"))
                    )
                except ImportError:
                    pass
                except Exception as exc:  # noqa: BLE001
                    errs.append(f"phase4a extra jsonschema {extra.name}: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase4a}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase4a} verdict={data.get('verdict')}")

    from bite_bench.phase4b import validate_phase4b_freeze

    phase4b_freeze = args.root / "benchmarks" / "spec" / "phase4b-scorer-addendum-freeze.json"
    if phase4b_freeze.is_file():
        n_checked += 1
        data = json.loads(phase4b_freeze.read_text(encoding="utf-8"))
        errs = list(validate_phase4b_freeze(data))
        schema_path = args.root / "spec" / "phase4b-scorer-addendum-freeze.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase4b freeze jsonschema: {exc}")
        for extra, extra_schema in (
            (
                args.root / "corpora" / "realstruct-1" / "annotations-v2.json",
                args.root / "spec" / "phase4a-realstruct1-annotations-v2.schema.json",
            ),
            (
                args.root / "artifacts" / "phase4b" / "annotation-diff.json",
                args.root / "spec" / "phase4b-annotation-diff.schema.json",
            ),
        ):
            if extra.is_file() and extra_schema.is_file():
                extra_doc = json.loads(extra.read_text(encoding="utf-8"))
                try:
                    import jsonschema  # type: ignore

                    jsonschema.validate(
                        extra_doc, json.loads(extra_schema.read_text(encoding="utf-8"))
                    )
                except ImportError:
                    pass
                except Exception as exc:  # noqa: BLE001
                    errs.append(f"phase4b extra jsonschema {extra.name}: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase4b_freeze}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase4b_freeze} verdict={data.get('verdict')}")

    from bite_eval.phase4b_eval import validate_phase4b_result

    phase4b = args.root / "artifacts" / "phase4b" / "real-adapter.json"
    if phase4b.is_file():
        n_checked += 1
        data = json.loads(phase4b.read_text(encoding="utf-8"))
        errs = list(validate_phase4b_result(data))
        errs.extend(_scan_secrets(data))
        schema_path = args.root / "spec" / "phase4b-real-adapter.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase4b jsonschema: {exc}")
        lock_path = args.root / "artifacts" / "phase4b" / "evaluation-lock.json"
        lock_schema = args.root / "spec" / "phase4b-evaluation-lock.schema.json"
        if lock_path.is_file() and lock_schema.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(
                    json.loads(lock_path.read_text(encoding="utf-8")),
                    json.loads(lock_schema.read_text(encoding="utf-8")),
                )
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase4b extra jsonschema {lock_path.name}: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase4b}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase4b} verdict={data.get('verdict')}")

    from bite_bench.phase4c import validate_phase4c_freeze

    phase4c_freeze = args.root / "benchmarks" / "spec" / "phase4c-holdout-first-open-freeze.json"
    if phase4c_freeze.is_file():
        n_checked += 1
        data = json.loads(phase4c_freeze.read_text(encoding="utf-8"))
        errs = list(validate_phase4c_freeze(data))
        schema_path = args.root / "spec" / "phase4c-holdout-first-open-freeze.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase4c freeze jsonschema: {exc}")
        eq_path = args.root / "artifacts" / "phase4c" / "reachability-equivalence.json"
        eq_schema = args.root / "spec" / "phase4c-reachability-equivalence.schema.json"
        if eq_path.is_file() and eq_schema.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(
                    json.loads(eq_path.read_text(encoding="utf-8")),
                    json.loads(eq_schema.read_text(encoding="utf-8")),
                )
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase4c extra jsonschema {eq_path.name}: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase4c_freeze}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase4c_freeze} verdict={data.get('verdict')}")

    from bite_eval.phase4c_eval import validate_phase4c_result

    phase4c = args.root / "artifacts" / "phase4c" / "real-holdout.json"
    if phase4c.is_file():
        n_checked += 1
        data = json.loads(phase4c.read_text(encoding="utf-8"))
        errs = list(validate_phase4c_result(data))
        schema_path = args.root / "spec" / "phase4c-real-holdout.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase4c jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase4c}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase4c} verdict={data.get('verdict')}")

    from bite_bench.phase4d import validate_phase4d_freeze

    phase4d_freeze = args.root / "benchmarks" / "spec" / "phase4d-measurement-semantics-freeze.json"
    if phase4d_freeze.is_file():
        n_checked += 1
        data = json.loads(phase4d_freeze.read_text(encoding="utf-8"))
        errs = list(validate_phase4d_freeze(data))
        schema_path = args.root / "spec" / "phase4d-measurement-semantics-freeze.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase4d freeze jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase4d_freeze}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase4d_freeze} verdict={data.get('verdict')}")

    from bite_eval.phase4d_audit import validate_phase4d_result

    phase4d = args.root / "artifacts" / "phase4d" / "measurement-semantics.json"
    if phase4d.is_file():
        n_checked += 1
        data = json.loads(phase4d.read_text(encoding="utf-8"))
        errs = list(validate_phase4d_result(data))
        schema_path = args.root / "spec" / "phase4d-measurement-semantics.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase4d jsonschema: {exc}")
        atom_path = args.root / "artifacts" / "phase4d" / "atom-aware-reference.json"
        atom_schema = args.root / "spec" / "phase4d-atom-aware-reference.schema.json"
        if atom_path.is_file() and atom_schema.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(
                    json.loads(atom_path.read_text(encoding="utf-8")),
                    json.loads(atom_schema.read_text(encoding="utf-8")),
                )
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase4d extra jsonschema {atom_path.name}: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase4d}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase4d} verdict={data.get('verdict')}")

    from bite_bench.phase4e import validate_phase4e_freeze

    phase4e_freeze = args.root / "benchmarks" / "spec" / "phase4e-full-key-reference-freeze.json"
    if phase4e_freeze.is_file():
        n_checked += 1
        data = json.loads(phase4e_freeze.read_text(encoding="utf-8"))
        errs = list(validate_phase4e_freeze(data))
        schema_path = args.root / "spec" / "phase4e-full-key-reference-freeze.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase4e freeze jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase4e_freeze}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase4e_freeze} verdict={data.get('verdict')}")

    from bite_bench.phase4f import validate_phase4f_freeze

    phase4f_freeze = args.root / "benchmarks" / "spec" / "phase4f-prospective-comparison-freeze.json"
    if phase4f_freeze.is_file():
        n_checked += 1
        data = json.loads(phase4f_freeze.read_text(encoding="utf-8"))
        errs = list(validate_phase4f_freeze(data))
        schema_path = args.root / "spec" / "phase4f-prospective-comparison-freeze.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase4f freeze jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase4f_freeze}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase4f_freeze} verdict={data.get('verdict')}")

    from bite_eval.phase4e_eval import validate_phase4e_result

    phase4e = args.root / "artifacts" / "phase4e" / "full-key-reference.json"
    if phase4e.is_file():
        n_checked += 1
        data = json.loads(phase4e.read_text(encoding="utf-8"))
        errs = list(validate_phase4e_result(data))
        schema_path = args.root / "spec" / "phase4e-full-key-reference.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase4e jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase4e}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase4e} verdict={data.get('verdict')}")

    from bite_eval.phase4f_eval import validate_phase4f_result

    phase4f = args.root / "artifacts" / "phase4f" / "prospective-comparison.json"
    if phase4f.is_file():
        n_checked += 1
        data = json.loads(phase4f.read_text(encoding="utf-8"))
        errs = list(validate_phase4f_result(data))
        schema_path = args.root / "spec" / "phase4f-prospective-comparison.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase4f jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase4f}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase4f} verdict={data.get('verdict')}")

    from bite_bench.phase4g import validate_phase4g_freeze

    phase4g_freeze = args.root / "benchmarks" / "spec" / "phase4g-comparison-accounting-freeze.json"
    if phase4g_freeze.is_file():
        n_checked += 1
        data = json.loads(phase4g_freeze.read_text(encoding="utf-8"))
        errs = list(validate_phase4g_freeze(data))
        schema_path = args.root / "spec" / "phase4g-comparison-accounting-freeze.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase4g freeze jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase4g_freeze}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase4g_freeze} verdict={data.get('verdict')}")

    from bite_eval.phase4g_eval import validate_phase4g_result

    phase4g = args.root / "artifacts" / "phase4g" / "comparison-accounting.json"
    if phase4g.is_file():
        n_checked += 1
        data = json.loads(phase4g.read_text(encoding="utf-8"))
        errs = list(validate_phase4g_result(data))
        schema_path = args.root / "spec" / "phase4g-comparison-accounting.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase4g jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase4g}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase4g} verdict={data.get('verdict')}")

    from bite_bench.phase4h import validate_phase4h_freeze

    phase4h_freeze = args.root / "benchmarks" / "spec" / "phase4h-realstruct2-freeze.json"
    if phase4h_freeze.is_file():
        n_checked += 1
        data = json.loads(phase4h_freeze.read_text(encoding="utf-8"))
        errs = list(validate_phase4h_freeze(data))
        schema_path = args.root / "spec" / "phase4h-realstruct2-freeze.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase4h freeze jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase4h_freeze}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase4h_freeze} verdict={data.get('verdict')}")

    from bite_bench.realstruct2 import validate_candidate_pool

    phase4h_pool = args.root / "artifacts" / "phase4h" / "candidate-pool.json"
    if phase4h_pool.is_file():
        n_checked += 1
        data = json.loads(phase4h_pool.read_text(encoding="utf-8"))
        errs = list(validate_candidate_pool(data))
        schema_path = args.root / "spec" / "phase4h-candidate-pool.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase4h pool jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase4h_pool}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase4h_pool} verdict={data.get('verdict')}")

    from bite_bench.realstruct2 import validate_phase4h_corpus

    phase4h = args.root / "artifacts" / "phase4h" / "realstruct-2.json"
    if phase4h.is_file():
        n_checked += 1
        data = json.loads(phase4h.read_text(encoding="utf-8"))
        errs = list(validate_phase4h_corpus(data))
        schema_path = args.root / "spec" / "phase4h-realstruct2.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase4h jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase4h}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase4h} verdict={data.get('verdict')}")

    from bite_bench.phase4h2 import validate_phase4h2_freeze

    phase4h2_freeze = args.root / "benchmarks" / "spec" / "phase4h2-acquisition-extension-freeze.json"
    if phase4h2_freeze.is_file():
        n_checked += 1
        data = json.loads(phase4h2_freeze.read_text(encoding="utf-8"))
        errs = list(validate_phase4h2_freeze(data))
        schema_path = args.root / "spec" / "phase4h2-acquisition-extension-freeze.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase4h2 freeze jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase4h2_freeze}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase4h2_freeze} verdict={data.get('verdict')}")

    from bite_bench.realstruct2_ext import validate_extension_pool

    phase4h2_pool = args.root / "artifacts" / "phase4h2" / "extension-pool.json"
    if phase4h2_pool.is_file():
        n_checked += 1
        data = json.loads(phase4h2_pool.read_text(encoding="utf-8"))
        errs = list(validate_extension_pool(data))
        schema_path = args.root / "spec" / "phase4h2-extension-pool.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase4h2 pool jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase4h2_pool}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase4h2_pool} verdict={data.get('verdict')}")

    from bite_bench.phase4i import validate_phase4i_freeze

    phase4i_freeze = args.root / "benchmarks" / "spec" / "phase4i-first-open-freeze.json"
    if phase4i_freeze.is_file():
        n_checked += 1
        data = json.loads(phase4i_freeze.read_text(encoding="utf-8"))
        errs = list(validate_phase4i_freeze(data))
        schema_path = args.root / "spec" / "phase4i-first-open-freeze.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase4i freeze jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase4i_freeze}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase4i_freeze} verdict={data.get('verdict')}")

    from bite_bench.realstruct2_ext import validate_augmented

    phase4h2 = args.root / "artifacts" / "phase4h2" / "realstruct-2-augmented.json"
    if phase4h2.is_file():
        n_checked += 1
        data = json.loads(phase4h2.read_text(encoding="utf-8"))
        errs = list(validate_augmented(data))
        schema_path = args.root / "spec" / "phase4h2-realstruct2-augmented.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase4h2 jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase4h2}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase4h2} verdict={data.get('verdict')}")

    from bite_eval.phase4i_eval import validate_phase4i_result

    phase4i = args.root / "artifacts" / "phase4i" / "first-open.json"
    if phase4i.is_file():
        n_checked += 1
        data = json.loads(phase4i.read_text(encoding="utf-8"))
        errs = list(validate_phase4i_result(data))
        schema_path = args.root / "spec" / "phase4i-first-open.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase4i jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase4i}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase4i} verdict={data.get('verdict')}")

    from bite_bench.phase4j import validate_phase4j_freeze

    phase4j_freeze = args.root / "benchmarks" / "spec" / "phase4j-reference-schema-freeze.json"
    if phase4j_freeze.is_file():
        n_checked += 1
        data = json.loads(phase4j_freeze.read_text(encoding="utf-8"))
        errs = list(validate_phase4j_freeze(data))
        schema_path = args.root / "spec" / "phase4j-reference-schema-freeze.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase4j freeze jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase4j_freeze}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase4j_freeze} verdict={data.get('verdict')}")

    from bite_eval.phase4j_audit import validate_phase4j_result

    phase4j = args.root / "artifacts" / "phase4j" / "reference-schema-audit.json"
    if phase4j.is_file():
        n_checked += 1
        data = json.loads(phase4j.read_text(encoding="utf-8"))
        errs = list(validate_phase4j_result(data))
        schema_path = args.root / "spec" / "phase4j-reference-schema-audit.schema.json"
        if schema_path.is_file():
            try:
                import jsonschema  # type: ignore

                jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
            except ImportError:
                pass
            except Exception as exc:  # noqa: BLE001
                errs.append(f"phase4j jsonschema: {exc}")
        if errs:
            failed += 1
            print(f"FAIL {phase4j}:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {phase4j} verdict={data.get('verdict')}")

    if n_checked == 0:
        print("No artifacts to validate", file=sys.stderr)
        return 1
    print(f"Validated {n_checked} artifacts; failures={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
