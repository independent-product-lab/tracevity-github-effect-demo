#!/usr/bin/env bash
set -euo pipefail

work="${1:-work/reference}"
issue_number="${2:-1}"

case "$work" in
  ""|"/"|"."|"..") echo "Unsafe output directory: $work" >&2; exit 1 ;;
esac
if [[ -e "$work" ]]; then
  echo "Output directory must not already exist: $work" >&2
  exit 1
fi
mkdir -p "$work"
cp requirements.json "$work/requirements.json"

run_variant() {
  local variant="$1"
  local directory="$work/$variant"
  mkdir -p "$directory"

  tracevity capture otlp \
    --listen 127.0.0.1:4318 \
    --out "$directory/trace.otlp.pb" \
    --receipt "$directory/capture-receipt.json" \
    --idle-timeout 60 \
    >"$directory/capture.stdout.jsonl" \
    2>"$directory/capture.stderr" &
  local capture_pid=$!
  local ready=0
  for _attempt in $(seq 1 100); do
    if grep -q '"status": "LISTENING"' "$directory/capture.stdout.jsonl" 2>/dev/null; then
      ready=1
      break
    fi
    if ! kill -0 "$capture_pid" 2>/dev/null; then
      break
    fi
    sleep 0.1
  done
  if [[ "$ready" -ne 1 ]]; then
    wait "$capture_pid" || true
    echo "Tracevity capture did not become ready" >&2
    exit 1
  fi

  python scripts/create_effect.py \
    --variant "$variant" \
    --repository "$GITHUB_REPOSITORY" \
    --issue-number "$issue_number" \
    --out "$directory/effect.json"
  wait "$capture_pid"

  python scripts/prepare_inputs.py manifest \
    --variant "$variant" \
    --artifact "$directory/trace.otlp.pb" \
    --receipt "$directory/capture-receipt.json" \
    --effect "$directory/effect.json" \
    --out "$directory/manifest.json"
  local comment_id
  comment_id="$(python -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["comment_id"])' "$directory/effect.json")"
  TRACEVITY_GITHUB_TOKEN="$GITHUB_TOKEN" tracevity evidence github issue-comment \
    --repo "$GITHUB_REPOSITORY" \
    --comment-id "$comment_id" \
    --out "$directory/evidence.json"
  set +e
  tracevity inspect \
    --manifest "$directory/manifest.json" \
    --requirements "$work/requirements.json" \
    --evidence "$directory/evidence.json" \
    --out "$directory/reconstruction-report.json"
  local inspect_exit=$?
  set -e
  local expected_inspect_exit=0
  if [[ "$variant" == "broken" ]]; then
    expected_inspect_exit=2
  fi
  if [[ "$inspect_exit" -ne "$expected_inspect_exit" ]]; then
    echo "$variant Inspect returned $inspect_exit; expected $expected_inspect_exit" >&2
    exit 1
  fi
  tracevity report render "$directory/reconstruction-report.json" \
    --html "$directory/reconstruction-report.html" \
    --markdown "$directory/reconstruction-report.md"
}

run_variant baseline
run_variant broken
run_variant repaired

python scripts/prepare_inputs.py suite --candidate broken --out "$work/gate-broken.json"
python scripts/prepare_inputs.py suite --candidate repaired --out "$work/gate-repaired.json"

set +e
tracevity gate --suite "$work/gate-broken.json" --out "$work/gate-broken-report.json"
broken_exit=$?
set -e
if [[ "$broken_exit" -ne 2 ]]; then
  echo "Broken candidate returned $broken_exit; expected Gate exit 2" >&2
  exit 1
fi
tracevity report render "$work/gate-broken-report.json" \
  --html "$work/gate-broken-report.html" \
  --markdown "$work/gate-broken-report.md"

tracevity gate --suite "$work/gate-repaired.json" --out "$work/gate-repaired-report.json"
tracevity report render "$work/gate-repaired-report.json" \
  --html "$work/gate-repaired-report.html" \
  --markdown "$work/gate-repaired-report.md"

python scripts/verify_results.py "$work" --summary "$work/reference-summary.json"
