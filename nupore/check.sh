#!/usr/bin/env bash
# Merge-Gate lokal UND in CI identisch (config/07).
# Nutzung: bash nupore/check.sh [graph-root]   (Default: graph)
set -euo pipefail

ROOT="${1:-graph}"
cd "$(dirname "$0")/.."

echo "== Validator =="
python3 -m nupore.graph.validate "$ROOT"

echo "== Index-Sync =="
python3 -m nupore.graph.build_index --check "$ROOT"

echo "OK: Merge-Gate bestanden ($ROOT)."
