"""
Test end-to-end scenario: create actors, run simulation, verify physics.

Usage:
    python tests/test_scenario.py [--host HOST] [--port PORT] [--map MAP]
"""

import argparse
import math
import sys
import time
from rpc_client import connect


def test_vehicle_acceleration_and_brake(proxy):
    """Test that a vehicle accelerates with throttle and stops with brake."""
    print("[TEST] Vehicle acceleration & braking...")
    proxy.sim.reset()

    lanes = proxy.map.lane.get_all(False, "CITY_DRIVING")
    lane_id = lanes[0]
    curve = proxy.map.lane.get_central_curve(lane_id)
    x, y = curve[len(curve) // 2]
    heading = proxy.map.get_lane_heading(lane_id, 0.0)

    proxy.sim.create_actor({
        "actor_id": "test_v",
        "actor_type": "vehicle.lincoln.mkz",
        "x": x, "y": y, "z": 0.0,
        "heading": heading
    })
    proxy.sim.set_actor_status("test_v", "ready")
    proxy.sim.start_scenario()

    # Accelerate
    for _ in range(100):
        proxy.sim.apply_vehicle_control("test_v", {
            "throttle": 1.0, "steer": 0.0, "brake": 0.0, "reverse": False
        })
        time.sleep(0.01)

    actor = proxy.sim.get_actor("test_v")
    speed_after_accel = actor["speed"]
    assert speed_after_accel > 0, f"Vehicle should be moving after throttle, speed={speed_after_accel}"
    print(f"  After acceleration: {speed_after_accel:.2f} m/s")

    # Brake
    for _ in range(200):
        proxy.sim.apply_vehicle_control("test_v", {
            "throttle": 0.0, "steer": 0.0, "brake": 1.0, "reverse": False
        })
        time.sleep(0.01)

    actor = proxy.sim.get_actor("test_v")
    speed_after_brake = actor["speed"]
    assert speed_after_brake < speed_after_accel, \
        f"Speed should decrease after braking: {speed_after_accel:.2f} -> {speed_after_brake:.2f}"
    print(f"  After braking: {speed_after_brake:.2f} m/s")

    proxy.sim.stop_scenario()
    print("  OK - Acceleration and braking work correctly")
    return True


def test_vehicle_steering(proxy):
    """Test that steering changes vehicle heading."""
    print("[TEST] Vehicle steering...")
    proxy.sim.reset()

    lanes = proxy.map.lane.get_all(False, "CITY_DRIVING")
    lane_id = lanes[0]
    curve = proxy.map.lane.get_central_curve(lane_id)
    x, y = curve[len(curve) // 2]
    heading = proxy.map.get_lane_heading(lane_id, 0.0)

    proxy.sim.create_actor({
        "actor_id": "steer_v",
        "actor_type": "vehicle.lincoln.mkz",
        "x": x, "y": y, "z": 0.0,
        "heading": heading
    })
    proxy.sim.set_actor_status("steer_v", "ready")
    proxy.sim.start_scenario()

    initial_heading = heading

    # Drive with steering
    for _ in range(200):
        proxy.sim.apply_vehicle_control("steer_v", {
            "throttle": 0.5, "steer": 0.5, "brake": 0.0, "reverse": False
        })
        time.sleep(0.01)

    actor = proxy.sim.get_actor("steer_v")
    final_heading = actor["location"]["yaw"]

    proxy.sim.stop_scenario()

    heading_diff = abs(final_heading - initial_heading)
    assert heading_diff > 0.01, f"Heading should change with steering, diff={heading_diff:.4f}"
    print(f"  Initial heading: {initial_heading:.4f}, Final: {final_heading:.4f}, "
          f"Diff: {heading_diff:.4f} rad")
    print("  OK - Steering affects heading")
    return True


def test_perfect_vehicle_heading(proxy):
    """Test that perfect vehicle directly sets heading."""
    print("[TEST] Perfect vehicle heading control...")
    proxy.sim.reset()

    lanes = proxy.map.lane.get_all(False, "CITY_DRIVING")
    lane_id = lanes[0]
    curve = proxy.map.lane.get_central_curve(lane_id)
    x, y = curve[len(curve) // 2]

    target_heading = 2.5

    proxy.sim.create_actor({
        "actor_id": "perfect_v",
        "actor_type": "vehicle.lincoln.mkz.perfect",
        "x": x, "y": y, "z": 0.0,
        "heading": 0.0
    })
    proxy.sim.set_actor_status("perfect_v", "ready")
    proxy.sim.start_scenario()

    for _ in range(50):
        proxy.sim.apply_vehicle_control("perfect_v", {
            "acceleration": 1.0,
            "heading": target_heading,
            "throttle": 0.0, "brake": 0.0, "steer": 0.0, "reverse": False
        })
        time.sleep(0.01)

    actor = proxy.sim.get_actor("perfect_v")
    proxy.sim.stop_scenario()

    actual_heading = actor["location"]["yaw"]
    heading_error = abs(actual_heading - target_heading)
    assert heading_error < 0.1, \
        f"Perfect vehicle heading should match target: expected={target_heading:.2f}, " \
        f"got={actual_heading:.2f}, error={heading_error:.4f}"
    print(f"  Target: {target_heading:.2f}, Actual: {actual_heading:.4f}, Error: {heading_error:.4f}")
    print("  OK - Perfect heading control works")
    return True


def test_multi_actor_scenario(proxy):
    """Test running a scenario with multiple actor types simultaneously."""
    print("[TEST] Multi-actor scenario...")
    proxy.sim.reset()

    lanes = proxy.map.lane.get_all(False, "CITY_DRIVING")
    lane_id = lanes[0]
    curve = proxy.map.lane.get_central_curve(lane_id)
    heading = proxy.map.get_lane_heading(lane_id, 0.0)

    # Create diverse actors
    actors_config = [
        ("car_1", "vehicle.lincoln.mkz", 0),
        ("car_2", "vehicle.lincoln.mkz.perfect", 20),
        ("bike_1", "vehicle.bicycle.normal", 40),
        ("ped_1", "walker.pedestrian.normal", 60),
    ]

    base_x, base_y = curve[len(curve) // 2]
    for actor_id, actor_type, offset in actors_config:
        proxy.sim.create_actor({
            "actor_id": actor_id,
            "actor_type": actor_type,
            "x": base_x + offset * math.cos(heading),
            "y": base_y + offset * math.sin(heading),
            "z": 0.0,
            "heading": heading
        })
        proxy.sim.set_actor_status(actor_id, "ready")

    # Add a traffic cone
    proxy.sim.create_actor({
        "actor_id": "cone_1",
        "actor_type": "static.traffic_cone",
        "x": base_x + 80 * math.cos(heading),
        "y": base_y + 80 * math.sin(heading),
        "z": 0.0,
        "heading": 0.0
    })

    # Add a traffic light
    proxy.sim.create_signal({
        "signal_id": "tl_1",
        "signal_type": "signal.traffic_light",
        "signal_state": "green"
    })

    proxy.sim.start_scenario()

    # Run for a bit with controls
    for i in range(100):
        proxy.sim.apply_vehicle_control("car_1", {
            "throttle": 0.5, "steer": 0.0, "brake": 0.0, "reverse": False
        })
        proxy.sim.apply_vehicle_control("car_2", {
            "acceleration": 1.5, "heading": heading,
            "throttle": 0.0, "brake": 0.0, "steer": 0.0, "reverse": False
        })
        proxy.sim.apply_vehicle_control("bike_1", {
            "throttle": 0.3, "steer": 0.0, "brake": 0.0, "reverse": False
        })
        proxy.sim.apply_walker_action("ped_1", {
            "acceleration": 1.0, "heading": heading
        })

        if i == 50:
            proxy.sim.set_signal_state("tl_1", "red")

        time.sleep(0.01)

    snapshot = proxy.sim.get_snapshot()
    proxy.sim.stop_scenario()

    assert len(snapshot["actors"]) == 5, f"Expected 5 actors, got {len(snapshot['actors'])}"
    assert len(snapshot["signals"]) == 1, f"Expected 1 signal, got {len(snapshot['signals'])}"

    for actor_id in ["car_1", "car_2", "bike_1", "ped_1"]:
        speed = snapshot["actors"][actor_id]["speed"]
        print(f"  {actor_id}: speed={speed:.2f} m/s")
        assert speed > 0, f"{actor_id} should be moving"

    cone_speed = snapshot["actors"]["cone_1"]["speed"]
    assert cone_speed == 0 or cone_speed == 0.0, f"Cone should not move, speed={cone_speed}"
    print(f"  cone_1: speed={cone_speed} (static)")

    tl_state = snapshot["signals"]["tl_1"]["state"]
    assert tl_state == "red", f"Traffic light should be red, got {tl_state}"
    print(f"  tl_1: state={tl_state}")

    print("  OK - Multi-actor scenario completed successfully")
    return True


def test_position_changes_with_movement(proxy):
    """Test that actor position actually changes when moving."""
    print("[TEST] Position changes with movement...")
    proxy.sim.reset()

    lanes = proxy.map.lane.get_all(False, "CITY_DRIVING")
    lane_id = lanes[0]
    curve = proxy.map.lane.get_central_curve(lane_id)
    x, y = curve[len(curve) // 2]
    heading = proxy.map.get_lane_heading(lane_id, 0.0)

    proxy.sim.create_actor({
        "actor_id": "pos_test",
        "actor_type": "vehicle.lincoln.mkz",
        "x": x, "y": y, "z": 0.0,
        "heading": heading
    })
    proxy.sim.set_actor_status("pos_test", "ready")

    initial = proxy.sim.get_actor("pos_test")
    init_x = initial["location"]["x"]
    init_y = initial["location"]["y"]

    proxy.sim.start_scenario()
    for _ in range(200):
        proxy.sim.apply_vehicle_control("pos_test", {
            "throttle": 0.8, "steer": 0.0, "brake": 0.0, "reverse": False
        })
        time.sleep(0.01)

    final = proxy.sim.get_actor("pos_test")
    proxy.sim.stop_scenario()

    final_x = final["location"]["x"]
    final_y = final["location"]["y"]
    distance = math.sqrt((final_x - init_x)**2 + (final_y - init_y)**2)

    assert distance > 1.0, f"Vehicle should have moved, distance={distance:.2f}"
    print(f"  Start: ({init_x:.1f}, {init_y:.1f})")
    print(f"  End:   ({final_x:.1f}, {final_y:.1f})")
    print(f"  Distance traveled: {distance:.2f} m")
    print("  OK")
    return True


def main():
    parser = argparse.ArgumentParser(description="Test end-to-end scenarios")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10667)
    parser.add_argument("--map", default="borregas_ave")
    args = parser.parse_args()

    proxy = connect(f"tcp://{args.host}:{args.port}")

    print(f"Loading map: {args.map}")
    proxy.load_map(args.map)
    print(f"Map loaded: {proxy.map.get_current_map()}\n")

    tests = [
        test_vehicle_acceleration_and_brake,
        test_vehicle_steering,
        test_perfect_vehicle_heading,
        test_multi_actor_scenario,
        test_position_changes_with_movement,
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
