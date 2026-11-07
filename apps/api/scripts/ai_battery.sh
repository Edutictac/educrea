#!/usr/bin/env bash
# Runs the AI battery with the dev environment (keys file, free models) without starting the API.
# The environment comes from the dev start script; its values are never printed.
set -euo pipefail
START=${EDUCREA_START_SCRIPT:-/tmp/educrea-api-start.sh}
cd "$(dirname "$0")/.."
[ -f "$START" ] || { echo "No encuentro $START (ver la memoria del entorno de desarrollo)" >&2; exit 2; }
# shellcheck disable=SC1090
source <(grep -v -E '^\s*(exec|cd)\b' "$START")
exec .venv/bin/python scripts/ai_battery.py "$@"
