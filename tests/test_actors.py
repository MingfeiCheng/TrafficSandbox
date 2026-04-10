"""
Test actor creation, control, and removal for all actor types.

Usage:
    python tests/test_actors.py [--host HOST] [--port PORT] [--map MAP]
"""

import argparse
import sys
import time
from rpc_client import connect


VEHICLE_TYPES = [
    "vehicle.lincoln.mkz",
    "vehicle.lincoln.mkz.perfect",
    "vehicle.lincoln.mkz_lgsvl",
    "vehicle.lincoln.mkz_lgsvl.perfect",
    "vehicle.bicycle.normal",
    "vehicle.bicycle.normal.perfect",
]

WALKER_TYPES = [
    "walker.pedestrian.normal",
]

STATIC_TYPES = [
    "static.traffic_cone",
]

SIGNAL_TYPES = [
    "signal.traffic_light",
]


def get_spawn_point(proxy):
    """Get a valid spawn point from the loaded map."""
    lanes = proxy.map.lane.get_all(False, "CITY_DRIVING")
    assert len(lanes) > 0, "No driving lanes found"
    lane_id = lanes[0]
    curve = proxy.map.lane.get_central_curve(lane_id)
    mid = len(curve) // 2
    x, y = curve[mid]
    heading = proxy.map.get_lane_heading(lane_id, 0.0)
    return x, y, heading


def test_create_all_vehicle_types(proxy):
    """Test creating each vehicle type."""
    print("[TEST] Create all vehicle types...")
    proxy.sim.reset()
    x, y, heading = get_spawn_point(proxy)

    for i, vtype in enumerate(VEHICLE_TYPES):
        actor_id = f"vehicle_{i}"
        result = proxy.sim.create_actor({
            "actor_id": actor_id,
            "actor_type": vtype,
            "x": x + i * 10,
            "y": y,
            "z": 0.0,
            "heading": heading
        })
        assert result["actor_id"] == actor_id, f"Actor ID mismatch: {result}"
        print(f"  Created {vtype} as {actor_id}")

    snapshot = proxy.sim.get_snapshot()
    assert len(snapshot["actors"]) == len(VEHICLE_TYPES), \
        f"Expected {len(VEHICLE_TYPES)} actors, got {len(snapshot['actors'])}"
    print(f"  OK - All {len(VEHICLE_TYPES)} vehicle types created")
    return True


def test_create_walker(proxy):
    """Test creating a pedestrian."""
    print("[TEST] Create walker...")
    proxy.sim.reset()
    x, y, heading = get_spawn_point(proxy)

    proxy.sim.create_actor({
        "actor_id": "walker_1",
        "actor_type": "walker.pedestrian.normal",
        "x": x, "y": y, "z": 0.0,
        "heading": heading
    })

    actor = proxy.sim.get_actor("walker_1")
    assert actor is not None, "Walker not found"
    print(f"  OK - Walker created at ({actor['location']['x']:.1f}, {actor['location']['y']:.1f})")
    return True


def test_create_static(proxy):
    """Test creating a static object."""
    print("[TEST] Create static object...")
    proxy.sim.reset()
    x, y, _ = get_spawn_point(proxy)

    proxy.sim.create_actor({
        "actor_id": "cone_1",
        "actor_type": "static.traffic_cone",
        "x": x, "y": y, "z": 0.0,
        "heading": 0.0
    })

    actor = proxy.sim.get_actor("cone_1")
    assert actor is not None, "Traffic cone not found"
    assert actor["speed"] == 0.0 or actor["speed"] == 0, "Static object should have speed 0"
    print(f"  OK - Traffic cone created")
    return True


def test_create_signal(proxy):
    """Test creating a traffic light signal."""
    print("[TEST] Create traffic signal...")
    proxy.sim.reset()

    proxy.sim.create_signal({
        "signal_id": "tl_1",
        "signal_type": "signal.traffic_light",
        "signal_state": "green"
    })

    signal = proxy.sim.get_signal("tl_1")
    assert signal is not None, "Signal not found"
    assert signal["state"] == "green", f"Expected green, got {signal['state']}"
    print(f"  OK - Traffic light created with state={signal['state']}")
    return True


def test_signal_state_changes(proxy):
    """Test changing traffic light states."""
    print("[TEST] Signal state changes...")
    proxy.sim.reset()

    proxy.sim.create_signal({
        "signal_id": "tl_1",
        "signal_type": "signal.traffic_light",
        "signal_state": "green"
    })

    for state in ["red", "yellow", "green"]:
        proxy.sim.set_signal_state("tl_1", state)
        signal = proxy.sim.get_signal("tl_1")
        assert signal["state"] == state, f"Expected {state}, got {signal['state']}"
        print(f"  State -> {state}: OK")

    print("  OK - All state transitions work")
    return True


def test_vehicle_control(proxy):
    """Test that vehicle control affects movement."""
    print("[TEST] Vehicle control (throttle)...")
    proxy.sim.reset()
    x, y, heading = get_spawn_point(proxy)

    proxy.sim.create_actor({
        "actor_id": "car_1",
        "actor_type": "vehicle.lincoln.mkz",
        "x": x, "y": y, "z": 0.0,
        "heading": heading
    })
    proxy.sim.set_actor_status("car_1", "ready")
    proxy.sim.start_scenario()

    # Apply throttle for a short duration
    for _ in range(50):
        proxy.sim.apply_vehicle_control("car_1", {
            "throttle": 0.8,
            "steer": 0.0,
            "brake": 0.0,
            "reverse": False
        })
        time.sleep(0.01)

    actor = proxy.sim.get_actor("car_1")
    proxy.sim.stop_scenario()

    assert actor["speed"] > 0, f"Vehicle should be moving, speed={actor['speed']}"
    print(f"  OK - Vehicle moving at {actor['speed']:.2f} m/s")
    return True


def test_walker_control(proxy):
    """Test that walker control affects movement."""
    print("[TEST] Walker control...")
    proxy.sim.reset()
    x, y, heading = get_spawn_point(proxy)

    proxy.sim.create_actor({
        "actor_id": "ped_1",
        "actor_type": "walker.pedestrian.normal",
        "x": x, "y": y, "z": 0.0,
        "heading": heading
    })
    proxy.sim.set_actor_status("ped_1", "ready")
    proxy.sim.start_scenario()

    for _ in range(50):
        proxy.sim.apply_walker_action("ped_1", {
            "acceleration": 2.0,
            "heading": heading
        })
        time.sleep(0.01)

    actor = proxy.sim.get_actor("ped_1")
    proxy.sim.stop_scenario()

    assert actor["speed"] > 0, f"Walker should be moving, speed={actor['speed']}"
    print(f"  OK - Walker moving at {actor['speed']:.2f} m/s")
    return True


def test_remove_actor(proxy):
    """Test removing actors."""
    print("[TEST] Remove actor...")
    proxy.sim.reset()
    x, y, heading = get_spawn_point(proxy)

    proxy.sim.create_actor({
        "actor_id": "temp_car",
        "actor_type": "vehicle.lincoln.mkz",
        "x": x, "y": y, "z": 0.0,
        "heading": heading
    })

    snapshot = proxy.sim.get_snapshot()
    assert "temp_car" in snapshot["actors"], "Actor should exist"

    proxy.sim.remove_actor("temp_car")

    snapshot = proxy.sim.get_snapshot()
    assert "temp_car" not in snapshot["actors"], "Actor should be removed"
    print("  OK - Actor removed successfully")
    return True


def test_remove_signal(proxy):
    """Test removing signals."""
    print("[TEST] Remove signal...")
    proxy.sim.reset()

    proxy.sim.create_signal({
        "signal_id": "tl_temp",
        "signal_type": "signal.traffic_light",
        "signal_state": "red"
    })

    snapshot = proxy.sim.get_snapshot()
    assert "tl_temp" in snapshot["signals"], "Signal should exist"

    proxy.sim.remove_signal("tl_temp")

    snapshot = proxy.sim.get_snapshot()
    assert "tl_temp" not in snapshot["signals"], "Signal should be removed"
    print("  OK - Signal removed successfully")
    return True


def test_static_teleport(proxy):
    """Test teleporting a static object."""
    print("[TEST] Static object teleport...")
    proxy.sim.reset()
    x, y, _ = get_spawn_point(proxy)

    proxy.sim.create_actor({
        "actor_id": "cone_tp",
        "actor_type": "static.traffic_cone",
        "x": x, "y": y, "z": 0.0,
        "heading": 0.0
    })

    new_x, new_y = x + 50.0, y + 50.0
    proxy.sim.set_static_location("cone_tp", {
        "x": new_x, "y": new_y, "z": 0.0,
        "pitch": 0.0, "yaw": 0.0, "roll": 0.0
    })

    actor = proxy.sim.get_actor("cone_tp")
    dx = abs(actor["location"]["x"] - new_x)
    dy = abs(actor["location"]["y"] - new_y)
    assert dx < 0.1 and dy < 0.1, f"Teleport failed: delta=({dx:.2f}, {dy:.2f})"
    print(f"  OK - Teleported to ({new_x:.1f}, {new_y:.1f})")
    return True


def test_actor_blueprint(proxy):
    """Test getting actor blueprints."""
    print("[TEST] Actor blueprints...")
    for vtype in VEHICLE_TYPES[:2]:
        bp = proxy.sim.get_actor_blueprint(vtype)
        assert bp is not None, f"No blueprint for {vtype}"
        print(f"  {vtype}: {bp}")
    print("  OK - Blueprints retrieved")
    return True


def main():
    parser = argparse.ArgumentParser(description="Test actor operations")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10667)
    parser.add_argument("--map", default="borregas_ave")
    args = parser.parse_args()

    proxy = connect(f"tcp://{args.host}:{args.port}")

    print(f"Loading map: {args.map}")
    proxy.load_map(args.map)
    print(f"Map loaded: {proxy.map.get_current_map()}\n")

    tests = [
        test_create_all_vehicle_types,
        test_create_walker,
        test_create_static,
        test_create_signal,
        test_signal_state_changes,
        test_vehicle_control,
        test_walker_control,
        test_remove_actor,
        test_remove_signal,
        test_static_teleport,
        test_actor_blueprint,
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

    proxy.sim.reset()

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
