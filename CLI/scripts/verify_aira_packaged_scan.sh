#!/usr/bin/env bash
#
# Lowest-risk packaged-path check: installs this package in a throwaway venv and
# exercises the real `aira` console script (`pip install -e .` → `aira scan`).
#
# Usage (from repo):
#   ./CLI/scripts/verify_aira_packaged_scan.sh
#   bash CLI/scripts/verify_aira_packaged_scan.sh
#
# Requirements: python3 on PATH, network for pip (first run / cold cache).
#
set -euo pipefail

CLI_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKDIR="$(mktemp -d)"
cleanup() { rm -rf "$WORKDIR"; }
trap cleanup EXIT

VENV="$WORKDIR/venv"
python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install -q --upgrade pip
"$VENV/bin/pip" install -q -e "$CLI_ROOT"

AIRA="$VENV/bin/aira"
SCAN_TARGET="$WORKDIR/tiny_scan_target.py"
printf '%s\n' 'def okay():' '    return True' >"$SCAN_TARGET"

SUCCESS_OUT="$WORKDIR/success.stdout"
SUCCESS_ERR="$WORKDIR/success.stderr"
set +e
"$AIRA" scan "$SCAN_TARGET" --output json --engine static >"$SUCCESS_OUT" 2>"$SUCCESS_ERR"
EC_SUCCESS=$?
set -e

if [[ "$EC_SUCCESS" -ne 0 ]]; then
	echo "FAIL: packaged scan expected exit 0, got $EC_SUCCESS" >&2
	cat "$SUCCESS_ERR" >&2
	exit 1
fi

export VERIFY_AIRA_JSON="$SUCCESS_OUT"
"$VENV/bin/python" -c 'import json, os

path = os.environ["VERIFY_AIRA_JSON"]
with open(path, encoding="utf-8") as handle:
	data = json.load(handle)
scan = data.get("aira_scan")
assert scan is not None, "top-level aira_scan missing"
summary = scan.get("summary") or {}
assert summary.get("files_scanned", 0) >= 1, "expected at least one file scanned"
'

MISSING="$WORKDIR/does_not_exist_for_aira_verify.py"
MISS_OUT="$WORKDIR/miss.stdout"
MISS_ERR="$WORKDIR/miss.stderr"
set +e
"$AIRA" scan "$MISSING" --output json --engine static >"$MISS_OUT" 2>"$MISS_ERR"
EC_MISS=$?
set -e

if [[ "$EC_MISS" -ne 3 ]]; then
	echo "FAIL: missing path expected exit 3, got $EC_MISS" >&2
	cat "$MISS_ERR" >&2
	exit 1
fi

if ! grep -Fq "Invalid scan target" "$MISS_ERR"; then
	echo "FAIL: stderr should contain substring: Invalid scan target" >&2
	cat "$MISS_ERR" >&2
	exit 1
fi

echo "verify_aira_packaged_scan: OK (aira scan packaged path: exit 0 + JSON stdout; missing path: exit 3 + expected stderr)"
