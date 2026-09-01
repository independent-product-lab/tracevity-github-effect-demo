#!/usr/bin/env python3
"""Verify the public demonstration's exact semantic outcomes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path} is not an object")
    return value


def requirement(report: dict[str, object], evidence: str) -> dict[str, object]:
    values = report.get("requirements")
    if not isinstance(values, list):
        raise AssertionError("report requirements missing")
    matches = [item for item in values if isinstance(item, dict) and item.get("evidence") == evidence]
    if len(matches) != 1:
        raise AssertionError(f"expected one {evidence} result")
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("work", type=Path)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    work = args.work
    baseline = load(work / "baseline/reconstruction-report.json")
    broken = load(work / "broken/reconstruction-report.json")
    repaired = load(work / "repaired/reconstruction-report.json")
    baseline_effect = requirement(baseline, "external_effect_state")
    broken_effect = requirement(broken, "external_effect_state")
    repaired_effect = requirement(repaired, "external_effect_state")
    assurance = baseline_effect.get("assurance")
    assert baseline_effect.get("result") == "ESTABLISHED"
    assert isinstance(assurance, dict)
    assert assurance.get("correlation") == "EXACT"
    assert assurance.get("source_independence") == ["EXTERNAL_SYSTEM_RECORD"]
    assert assurance.get("acquisition_provenance") == ["LOCAL_ADAPTER_PROVIDER_API"]
    assert assurance.get("record_authenticity") == "UNVERIFIED"
    assert broken_effect.get("result") != "ESTABLISHED"
    assert repaired_effect.get("result") == "ESTABLISHED"

    broken_gate = load(work / "gate-broken-report.json")
    repaired_gate = load(work / "gate-repaired-report.json")
    assert isinstance(broken_gate.get("summary"), dict)
    assert isinstance(repaired_gate.get("summary"), dict)
    assert broken_gate["summary"].get("verdict") == "FAIL_RECONSTRUCTION_REGRESSION"
    assert repaired_gate["summary"].get("verdict") == "PASS"
    changes = broken_gate.get("cases", [{}])[0].get("changes", [])
    assert any(
        isinstance(change, dict)
        and change.get("requirement_id") in {"downstream_correlation", "external_effect_state"}
        and change.get("classification") == "REGRESSION"
        for change in changes
    )

    comments = {}
    artifacts = {}
    for variant in ("baseline", "broken", "repaired"):
        effect = load(work / variant / "effect.json")
        receipt = load(work / variant / "capture-receipt.json")
        evidence = load(work / variant / "evidence.json")
        assert effect.get("runtime") == {"name": "mlflow-tracing", "version": "3.15.2"}
        assert receipt.get("trace_count") == 1 and receipt.get("span_count", 0) >= 2
        record = evidence.get("records", [{}])[0]
        assert record.get("source_independence") == "EXTERNAL_SYSTEM_RECORD"
        assert record.get("acquisition_provenance") == "LOCAL_ADAPTER_PROVIDER_API"
        assert record.get("record_authenticity") == "UNVERIFIED"
        comment_id = effect.get("comment_id")
        comment_url = effect.get("html_url")
        assert isinstance(comment_id, int) and comment_id > 0
        assert isinstance(comment_url, str) and comment_url.endswith(
            f"#issuecomment-{comment_id}"
        )
        comments[variant] = {"id": comment_id, "url": comment_url}
        for name in (
            "trace.otlp.pb",
            "capture-receipt.json",
            "evidence.json",
            "reconstruction-report.json",
            "reconstruction-report.html",
            "reconstruction-report.md",
        ):
            path = work / variant / name
            assert path.is_file() and path.stat().st_size > 0
            artifacts[f"{variant}/{name}"] = hashlib.sha256(path.read_bytes()).hexdigest()
    assert len({comment["id"] for comment in comments.values()}) == 3
    for name in (
        "gate-broken-report.json",
        "gate-broken-report.html",
        "gate-broken-report.md",
        "gate-repaired-report.json",
        "gate-repaired-report.html",
        "gate-repaired-report.md",
    ):
        path = work / name
        assert path.is_file() and path.stat().st_size > 0
        artifacts[name] = hashlib.sha256(path.read_bytes()).hexdigest()

    summary = {
        "schema_version": "0.1",
        "classification": "PUBLIC_DEMONSTRATION_NOT_CUSTOMER_PRODUCTION",
        "runtime": {"name": "mlflow-tracing", "version": "3.15.2"},
        "tracevity": "0.5.2",
        "adapter": {"id": "github.issue-comment", "version": "0.1"},
        "comments": comments,
        "baseline": {"external_effect_state": "ESTABLISHED", "authenticity": "UNVERIFIED"},
        "broken_gate": "FAIL_RECONSTRUCTION_REGRESSION",
        "repaired_gate": "PASS",
        "artifacts_sha256": dict(sorted(artifacts.items())),
        "limitations": [
            "This is public demonstration activity, not customer production evidence.",
            "The provider record is exactly correlated and read through GitHub's API; its authenticity is not cryptographically verified.",
            "The completeness declaration is bounded to this one configured workflow and exporter flush.",
        ],
    }
    if args.summary.exists():
        raise SystemExit(f"refusing to overwrite {args.summary}")
    args.summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "REFERENCE_WORKFLOW_VERIFIED", **summary}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
