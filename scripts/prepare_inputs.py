#!/usr/bin/env python3
"""Prepare exact Tracevity manifests and Gate suites from runtime receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path


DIALECT = {
    "name": "mlflow_native",
    "declared_version": "3.15.2",
    "binding_id": "binding-mlflow-native-to-otlp",
}


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"{path} must contain an object")
    return value


def write_new(path: Path, value: dict[str, object]) -> None:
    if path.exists():
        raise SystemExit(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def manifest(args: argparse.Namespace) -> None:
    receipt = read_json(args.receipt)
    effect = read_json(args.effect)
    raw = args.artifact.read_bytes()
    trace_ids = receipt.get("trace_ids")
    if not isinstance(trace_ids, list) or len(trace_ids) != 1 or not isinstance(trace_ids[0], str):
        raise SystemExit("capture receipt must identify exactly one trace")
    if receipt.get("artifact_sha256") != hashlib.sha256(raw).hexdigest():
        raise SystemExit("capture receipt digest does not match the artifact")
    if effect.get("variant") != args.variant:
        raise SystemExit("effect variant mismatch")
    value = {
        "schema_version": "0.2",
        "manifest_id": f"github-effect-{args.variant}-mlflow-3.15.2",
        "target_trace_id": trace_ids[0],
        "artifact": {
            "path": args.artifact.name,
            "sha256": receipt["artifact_sha256"],
            "transport": "OTLP",
            "encoding": "PROTOBUF",
            "signal_kind": "TRACES",
            "maximum_bytes": 8_388_608,
        },
        "dialect": DIALECT,
        "producer": {"system": "MLflow Tracing", "runtime_version": "3.15.2"},
        "capture": {
            "observed_at": receipt["observed_at"],
            "provenance": "Tracevity loopback capture of the real MLflow Tracing 3.15.2 OTLP HTTP/protobuf export produced by this demonstration run.",
            "completeness": "COMPLETE",
            "truncation": "NOT_OBSERVED",
            "notes": [
                "The demo creates one root trace, force-flushes the pinned exporter, admits one receiver request, and verifies one trace ID; this is bounded workflow evidence, not proof of arbitrary exporter completeness."
            ],
        },
    }
    write_new(args.out, value)


def suite(args: argparse.Namespace) -> None:
    candidate = args.candidate
    value = {
        "schema_version": "0.2",
        "suite_id": f"github-effect-{candidate}-gate",
        "suite_version": "0.2.0",
        "description": f"Compare the real correlated baseline with the {candidate} MLflow instrumentation path.",
        "evaluation_date": date.today().isoformat(),
        "cases": [
            {
                "case_id": f"github-effect-{candidate}",
                "description": "The GitHub action occurs in both runs; Gate evaluates whether the trace preserves the exact destination join.",
                "output_identity": f"github-effect-{candidate}-output",
                "requirements": "requirements.json",
                "baseline": {
                    "mode": "REPLAYABLE_INPUTS",
                    "manifest": "baseline/manifest.json",
                    "evidence": ["baseline/evidence.json"],
                    "expected_dialect": DIALECT,
                },
                "candidate": {
                    "manifest": f"{candidate}/manifest.json",
                    "evidence": [f"{candidate}/evidence.json"],
                    "expected_dialect": DIALECT,
                },
            }
        ],
        "policy": {
            "fail_recommended_regressions": False,
            "block_required_incomparable": True,
            "waivers": [],
        },
    }
    write_new(args.out, value)


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    manifest_parser = commands.add_parser("manifest")
    manifest_parser.add_argument("--variant", choices=["baseline", "broken", "repaired"], required=True)
    manifest_parser.add_argument("--artifact", type=Path, required=True)
    manifest_parser.add_argument("--receipt", type=Path, required=True)
    manifest_parser.add_argument("--effect", type=Path, required=True)
    manifest_parser.add_argument("--out", type=Path, required=True)
    suite_parser = commands.add_parser("suite")
    suite_parser.add_argument("--candidate", choices=["broken", "repaired"], required=True)
    suite_parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    manifest(args) if args.command == "manifest" else suite(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

