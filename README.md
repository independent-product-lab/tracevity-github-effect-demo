# Tracevity GitHub external-effect demonstration

This public reference workflow exercises one exact path:

```text
MLflow Tracing 3.15.2
→ real OTLP HTTP/protobuf export
→ Tracevity loopback capture
→ real GitHub issue comments
→ Tracevity GitHub issue-comment evidence adapter v0.1
→ Inspect + deterministic HTML/Markdown report
→ broken and repaired Gate comparisons
```

It demonstrates a narrow but consequential result: the GitHub action can still happen and the OTLP can still be valid while a release loses the identifier needed to reconstruct the external effect.

## Run the public black-box workflow

1. Fork or clone this repository into a GitHub repository where Actions may comment on issues.
2. Create one issue and note its number.
3. Open **Actions → Public Tracevity GitHub-effect acceptance → Run workflow**.
4. Enter the issue number.
5. Download the workflow artifact after the job completes.

The workflow installs `tracevity==0.5.6` from public PyPI and `mlflow-tracing==3.15.2`. It does not check out or access Tracevity's private source repository. Its only write authority is the repository-scoped `GITHUB_TOKEN`, with `contents: read` and `issues: write`. It runs only by explicit `workflow_dispatch`; untrusted fork pull requests never receive the write-enabled job.

## Expected outcomes

| Run | GitHub comment | Valid MLflow OTLP | Comment ID retained in trace | Reconstruction | Gate |
| --- | --- | --- | --- | --- | --- |
| Baseline | created | yes | yes | external effect established to the declared assurance | baseline |
| Broken | created | yes | no | destination record exists but cannot be joined | `FAIL_RECONSTRUCTION_REGRESSION` |
| Repaired | created | yes | yes | exact join restored | `PASS` |

The successful report says that Tracevity read an external GitHub destination record and correlated it to the trace by exact comment ID. The adapter acquisition is a provider API read, not cryptographic authenticity proof. TLS, ETag, and GitHub request identifiers do not make the record signed or independently verifiable.

## Command-specific network model

- `pip install` reads public PyPI.
- `tracevity capture otlp` listens only on `127.0.0.1`.
- `scripts/create_effect.py` performs the declared GitHub comment write.
- `tracevity evidence github issue-comment` performs one explicit read from `api.github.com`.
- `tracevity inspect`, `tracevity report render`, `tracevity traces list`, and `tracevity gate` make no network requests and contain no analytics.

The workflow uses no model API, Tracevity API, Tracevity secret, personal access token, hosted Inspector, or trace upload.

## Public evidence and privacy boundary

Each run exposes the real demo comments and retains its complete evidence bundle as a GitHub Actions artifact: captured OTLP, capture receipts, destination evidence envelopes, Reconstruction Reports, rendered HTML/Markdown, Gate inputs/reports, public object URLs, and SHA-256 digests. These are deliberately generated public demo artifacts, not customer production traces.

Never adapt this repository by posting private prompts, credentials, source code, logs, or production traces to a public issue or workflow artifact.

## Versions

- Tracevity CLI: `0.5.6`
- MLflow Tracing: `3.15.2`
- OTLP HTTP exporter: `1.44.0`
- Inspection Manifest: `0.2`
- Trace Reconstruction Requirements: `0.3`
- Correlated Evidence Envelope: `0.2`
- Reconstruction Report: `0.2`
- Gate Suite / Gate Report: `0.2`
- GitHub issue-comment evidence adapter: `0.1`

The authoritative machine-readable quickstart is at <https://tracevity.com/machine/quickstarts/github-effect.json>.
