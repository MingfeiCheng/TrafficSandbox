#!/usr/bin/env bash
# Run all test suites against a running TrafficSandbox instance.
#
# Usage:
#   ./tests/run_all.sh [HOST] [PORT] [MAP]
#
# Example:
#   ./tests/run_all.sh 127.0.0.1 10667 borregas_ave

set -e

HOST="${1:-127.0.0.1}"
PORT="${2:-10667}"
MAP="${3:-borregas_ave}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================"
echo "  TrafficSandbox Test Suite"
echo "  Host: $HOST:$PORT  |  Map: $MAP"
echo "============================================"
echo ""

TOTAL_PASSED=0
TOTAL_FAILED=0
SUITES=("test_connection" "test_map" "test_actors" "test_scenario")

for suite in "${SUITES[@]}"; do
    echo "--------------------------------------------"
    echo "  Running: ${suite}.py"
    echo "--------------------------------------------"

    if python "${suite}.py" --host "$HOST" --port "$PORT" --map "$MAP"; then
        echo ""
    else
        TOTAL_FAILED=$((TOTAL_FAILED + 1))
        echo "  >>> Suite ${suite} had failures <<<"
        echo ""
    fi
done

echo "============================================"
echo "  All test suites completed"
echo "============================================"

if [ "$TOTAL_FAILED" -gt 0 ]; then
    echo "  WARNING: $TOTAL_FAILED suite(s) had failures"
    exit 1
else
    echo "  All suites passed!"
    exit 0
fi
