#!/usr/bin/env python3
"""Create one safe GitHub comment inside a real MLflow 3.15.2 trace."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path


REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
VARIANTS = {"baseline", "broken", "repaired"}
API_VERSION = "2026-03-10"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=sorted(VARIANTS), required=True)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--issue-number", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def create_comment(repository: str, issue_number: int, body: str, token: str) -> dict[str, object]:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/issues/{issue_number}/comments",
        data=json.dumps({"body": body}, separators=(",", ":")).encode("utf-8"),
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "tracevity-github-effect-demo/0.1",
            "X-GitHub-Api-Version": API_VERSION,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status != 201:
                raise RuntimeError(f"GitHub returned HTTP {response.status}")
            raw = response.read(1_048_577)
    except urllib.error.URLError as error:
        raise RuntimeError("GitHub comment creation failed") from error
    if len(raw) > 1_048_576:
        raise RuntimeError("GitHub response exceeded the safe bound")
    value = json.loads(raw)
    if not isinstance(value, dict) or not isinstance(value.get("id"), int):
        raise RuntimeError("GitHub returned an invalid comment record")
    return value


def main() -> int:
    args = arguments()
    repository = args.repository or ""
    token = os.environ.get("GITHUB_TOKEN", "")
    if not REPOSITORY.fullmatch(repository):
        raise SystemExit("--repository must be OWNER/REPO")
    if args.issue_number < 1:
        raise SystemExit("--issue-number must be positive")
    if not token or "\n" in token or "\r" in token:
        raise SystemExit("GITHUB_TOKEN is required and must be header-safe")
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite {args.out}")
    args.out.parent.mkdir(parents=True, exist_ok=True)

    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    marker = f"tracevity-demo:{run_id}:{run_attempt}:{args.variant}"
    body = (
        "Tracevity public external-effect demonstration. "
        f"Marker `{marker}`. This is bounded demo activity, not customer production evidence."
    )

    os.environ.setdefault("MLFLOW_ENABLE_OTLP_EXPORTER", "true")
    os.environ.setdefault("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://127.0.0.1:4318/v1/traces")
    os.environ.setdefault("OTEL_EXPORTER_OTLP_TRACES_PROTOCOL", "http/protobuf")
    os.environ.setdefault("MLFLOW_TRACKING_URI", "http://127.0.0.1:1")
    os.environ.setdefault("OTEL_SDK_DISABLED", "false")

    import mlflow
    from mlflow.entities import SpanType
    from mlflow.tracing.provider import provider

    with mlflow.start_span(name="tracevity.github-effect", span_type=SpanType.AGENT) as agent:
        agent.set_inputs({"instruction": "Create the declared public demonstration comment."})
        with mlflow.start_span(name="github.create_issue_comment", span_type=SpanType.TOOL) as tool:
            tool.set_inputs(
                {
                    "repository": repository,
                    "issue_number": args.issue_number,
                    "marker": marker,
                }
            )
            comment = create_comment(repository, args.issue_number, body, token)
            comment_id = comment["id"]
            html_url = comment.get("html_url")
            if not isinstance(comment_id, int) or not isinstance(html_url, str):
                raise RuntimeError("GitHub response omitted the stable comment identity")
            tool.set_outputs({"comment_id": comment_id, "html_url": html_url, "status": "created"})
            if args.variant != "broken":
                tool.set_attribute("tracevity.external.operation.id", str(comment_id))
        agent.set_outputs({"status": "comment_created", "variant": args.variant})

    tracer_provider = provider.get()
    if tracer_provider is None or not tracer_provider.force_flush(timeout_millis=10_000):
        raise RuntimeError("MLflow OTLP provider did not flush")

    public_result = {
        "schema_version": "0.1",
        "variant": args.variant,
        "marker": marker,
        "repository": repository,
        "issue_number": args.issue_number,
        "comment_id": comment_id,
        "html_url": html_url,
        "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "correlation_recorded": args.variant != "broken",
        "runtime": {"name": "mlflow-tracing", "version": mlflow.__version__},
    }
    args.out.write_text(json.dumps(public_result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "COMMENT_CREATED", **public_result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

