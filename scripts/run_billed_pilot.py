#!/usr/bin/env python3
"""BITE-15 / BITE-15b billed synthetic pilot CLI (Z.ai target calls).

Default --minimal: 2 families × 3 instances × 2 methods = 12 target calls
(cost control). Expand toward N_pilot=24 later via --n-per-family / --families.

BITE-15b defaults write bite15b_* artifacts with per-call checkpoint + resume
so a mid-run TimeoutError cannot erase measured call counts.

Security:
  - Reads ZAI_API_KEY from env only (or via bw-env child process injection).
  - Never prints the key value; presence checks PRESENT/ABSENT (+ optional length).
  - On KEY_ABSENT: exit 2 with fixed message.
  - Stops on rate limit; writes partial artifact + summary.
  - Timeout: finite exponential backoff retries from config (no infinite storm).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

KEY_ABSENT_MSG = "KEY_ABSENT: need human finger to inject via bw-env/Bitwarden"

DEFAULT_CONFIG = Path("configs/pilot_bite15_billed.json")


def _load_config(path: Path | None) -> dict:
    if path is None:
        # Prefer CWD config, then package-relative
        for candidate in (DEFAULT_CONFIG, _ROOT / DEFAULT_CONFIG):
            if candidate.is_file():
                path = candidate
                break
    if path is None or not Path(path).is_file():
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BITE-15b billed synthetic pilot (Z.ai)")
    parser.add_argument(
        "--minimal",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="2 families × 3 instances × 2 methods (12 calls); default True",
    )
    parser.add_argument(
        "--n-per-family",
        type=int,
        default=None,
        help="Override instances per family (default 3 if --minimal else 24)",
    )
    parser.add_argument(
        "--families",
        nargs="*",
        default=None,
        help="Family ids (default: clean_local adversarial_omission if minimal)",
    )
    parser.add_argument(
        "--methods",
        nargs="*",
        default=["raw_full", "compressed_passthrough"],
        help="Method ids requiring target LLM calls",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Z.ai model id (default from config / glm-4.5-flash)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Pilot config JSON (default configs/pilot_bite15_billed.json)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("artifacts/pilot/bite15b_billed_summary.json"),
        help="Summary JSON output path (BITE-15b default)",
    )
    parser.add_argument(
        "--partial-out",
        type=Path,
        default=Path("artifacts/pilot/bite15b_billed_partial.json"),
        help="Running/partial JSON (atomic rewrite after each call)",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=Path("artifacts/pilot/bite15b_checkpoint.jsonl"),
        help="JSONL per-call checkpoint path",
    )
    parser.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Load checkpoint and skip already-ok calls (default True)",
    )
    parser.add_argument(
        "--timeout-s",
        type=float,
        default=None,
        help="Per-call read timeout seconds (default from config / 120)",
    )
    parser.add_argument(
        "--retry-max",
        type=int,
        default=None,
        help="Max timeout retries after first attempt (default from config / 3)",
    )
    parser.add_argument(
        "--slim",
        action="store_true",
        help="Omit per-instance results and http_trace from written JSON",
    )
    parser.add_argument(
        "--report-key-length",
        action="store_true",
        help="Include key length (not value) in presence report",
    )
    args = parser.parse_args(argv)

    from bite_eval.providers.zai_client import (
        DEFAULT_MODEL,
        DEFAULT_RETRY_BACKOFF_BASE_S,
        DEFAULT_RETRY_BACKOFF_FACTOR,
        DEFAULT_RETRY_MAX,
        DEFAULT_TIMEOUT_S,
        key_presence,
    )

    presence = key_presence(report_length=args.report_key_length)
    if presence["status"] == "ABSENT":
        print(KEY_ABSENT_MSG, file=sys.stderr)
        print(
            json.dumps({"key": presence, "exit": 2}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 2

    # Presence only — never the value
    print(json.dumps({"key": presence}, ensure_ascii=False))

    cfg = _load_config(args.config)
    provider_cfg = cfg.get("provider") if isinstance(cfg.get("provider"), dict) else {}
    retry_cfg = cfg.get("retry") if isinstance(cfg.get("retry"), dict) else {}

    from bite_eval.pilot.billed_runner import (
        MINIMAL_FAMILIES,
        MINIMAL_N_PER_FAMILY,
        N_PILOT_DEFAULT,
        run_billed_pilot,
        write_summary,
    )
    from bite_eval.providers.zai_client import ZaiClient

    model = args.model or provider_cfg.get("model") or DEFAULT_MODEL
    minimal = bool(args.minimal)
    if args.n_per_family is not None:
        n_per = args.n_per_family
    else:
        n_per = MINIMAL_N_PER_FAMILY if minimal else N_PILOT_DEFAULT

    families = args.families
    if families is None and minimal:
        families = list(MINIMAL_FAMILIES)

    timeout_s = (
        args.timeout_s
        if args.timeout_s is not None
        else float(retry_cfg.get("timeout_s", provider_cfg.get("timeout_s", DEFAULT_TIMEOUT_S)))
    )
    retry_max = (
        args.retry_max
        if args.retry_max is not None
        else int(retry_cfg.get("retry_max", DEFAULT_RETRY_MAX))
    )
    backoff_base = float(retry_cfg.get("retry_backoff_base_s", DEFAULT_RETRY_BACKOFF_BASE_S))
    backoff_factor = float(retry_cfg.get("retry_backoff_factor", DEFAULT_RETRY_BACKOFF_FACTOR))

    client = ZaiClient(
        model=model,
        timeout_s=timeout_s,
        retry_max=retry_max,
        retry_backoff_base_s=backoff_base,
        retry_backoff_factor=backoff_factor,
    )
    summary = run_billed_pilot(
        client=client,
        families=families,
        n_per_family=n_per,
        methods=tuple(args.methods),
        paid_api=True,
        model=model,
        minimal=minimal,
        stop_on_rate_limit=True,
        checkpoint_path=args.checkpoint,
        partial_path=args.partial_out,
        resume=bool(args.resume),
    )

    to_write = dict(summary)
    if args.slim:
        to_write.pop("results", None)
        to_write.pop("http_trace_redacted", None)

    if summary.get("rate_limited"):
        partial_path = write_summary(to_write, args.partial_out)
        # Also write a short sibling summary pointer
        write_summary(
            {
                "pilot_id": summary["pilot_id"],
                "decision": summary["decision"],
                "decision_reason": summary["decision_reason"],
                "rate_limited": True,
                "partial_path": str(partial_path),
                "checkpoint_path": str(args.checkpoint),
                "calls_succeeded": summary["calls_succeeded"],
                "calls_attempted": summary["calls_attempted"],
                "calls_skipped_ok": summary.get("calls_skipped_ok"),
            },
            args.out,
        )
        out_path = partial_path
    else:
        out_path = write_summary(to_write, args.out)

    print(
        json.dumps(
            {
                "decision": summary["decision"],
                "decision_reason": summary["decision_reason"],
                "paid_api": summary["paid_api"],
                "estimate_source": summary["estimate_source"],
                "model": summary["model"],
                "minimal": summary["minimal"],
                "resume": summary.get("resume"),
                "has_billed_usage": summary["has_billed_usage"],
                "rate_limited": summary["rate_limited"],
                "calls_attempted": summary["calls_attempted"],
                "calls_succeeded": summary["calls_succeeded"],
                "calls_skipped_ok": summary.get("calls_skipped_ok"),
                "calls_resumed_retry": summary.get("calls_resumed_retry"),
                "constraints_ok_rate": summary["constraints_ok_rate"],
                "n_instance_rows": summary["n_instance_rows"],
                "checkpoint": str(args.checkpoint),
                "partial_out": str(args.partial_out),
                "out": str(out_path),
                "timeout_s": timeout_s,
                "retry_max": retry_max,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
