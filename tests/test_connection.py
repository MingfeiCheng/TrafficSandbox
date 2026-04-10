"""
Test basic RPC connectivity and server health.

Usage:
    python tests/test_connection.py [--host HOST] [--port PORT]
"""

import argparse
import sys
import time
from rpc_client import connect


def test_connection(proxy):
    """Test that the RPC server is reachable."""
    print("[TEST] Connecting to RPC server...")
    result = proxy.sim.get_time()
    print(f"  OK - Server responded with frame={result['frame']}")
    return True


def test_reset(proxy):
    """Test sim.reset() clears all state."""
    print("[TEST] sim.reset()...")
    proxy.sim.reset()
    snapshot = proxy.sim.get_snapshot()
    assert len(snapshot["actors"]) == 0, f"Expected 0 actors, got {len(snapshot['actors'])}"
    assert len(snapshot["signals"]) == 0, f"Expected 0 signals, got {len(snapshot['signals'])}"
    print("  OK - Reset successful, no actors or signals")
    return True


def test_scenario_status(proxy):
    """Test scenario status transitions."""
    print("[TEST] Scenario status transitions...")
    proxy.sim.reset()

    status = proxy.sim.get_scenario_status()
    assert status == "waiting", f"Expected 'waiting', got '{status}'"
    print(f"  Initial status: {status}")

    proxy.sim.start_scenario()
    status = proxy.sim.get_scenario_status()
    assert status == "running", f"Expected 'running', got '{status}'"
    print(f"  After start: {status}")

    proxy.sim.stop_scenario()
    status = proxy.sim.get_scenario_status()
    assert status == "waiting", f"Expected 'waiting', got '{status}'"
    print(f"  After stop: {status}")

    print("  OK - Status transitions correct")
    return True


def test_time_advancing(proxy):
    """Test that game time advances when simulation is running."""
    print("[TEST] Time advancing...")
    proxy.sim.reset()
    proxy.sim.start_scenario()

    t1 = proxy.sim.get_time()
    time.sleep(0.2)
    t2 = proxy.sim.get_time()

    proxy.sim.stop_scenario()

    assert t2["frame"] > t1["frame"], f"Frame did not advance: {t1['frame']} -> {t2['frame']}"
    assert t2["game_time"] > t1["game_time"], "Game time did not advance"
    print(f"  OK - Frame {t1['frame']} -> {t2['frame']}, "
          f"game_time {t1['game_time']:.3f} -> {t2['game_time']:.3f}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Test RPC connectivity")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10667)
    args = parser.parse_args()

    proxy = connect(f"tcp://{args.host}:{args.port}")

    tests = [
        test_connection,
        test_reset,
        test_scenario_status,
        test_time_advancing,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn(proxy)
            passed += 1
        except Exception as e:
            print(f"  FAILED: {e}")
            failed += 1

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
