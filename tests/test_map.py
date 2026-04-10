"""
Test map loading and map query APIs.

Usage:
    python tests/test_map.py [--host HOST] [--port PORT] [--map MAP]
"""

import argparse
import sys
from rpc_client import connect


def test_load_map(proxy, map_name):
    """Test loading a map."""
    print(f"[TEST] Load map '{map_name}'...")
    proxy.load_map(map_name)
    current = proxy.map.get_current_map()
    assert current == map_name, f"Expected '{map_name}', got '{current}'"
    print(f"  OK - Map loaded: {current}")
    return True


def test_get_all_lanes(proxy):
    """Test retrieving all driving lanes."""
    print("[TEST] Get all driving lanes...")
    lanes = proxy.map.lane.get_all(False, "CITY_DRIVING")
    assert isinstance(lanes, list), f"Expected list, got {type(lanes)}"
    assert len(lanes) > 0, "No driving lanes found"
    print(f"  OK - Found {len(lanes)} driving lanes")
    print(f"  Sample lane IDs: {lanes[:3]}")
    return True


def test_get_all_lanes_with_junction(proxy):
    """Test retrieving lanes including junction lanes."""
    print("[TEST] Get lanes with junctions...")
    lanes_no_junction = proxy.map.lane.get_all(False, "CITY_DRIVING")
    lanes_with_junction = proxy.map.lane.get_all(True, "CITY_DRIVING")
    assert len(lanes_with_junction) >= len(lanes_no_junction), \
        "Including junctions should not reduce lane count"
    print(f"  Without junctions: {len(lanes_no_junction)}")
    print(f"  With junctions: {len(lanes_with_junction)}")
    print(f"  OK - Junction lanes: {len(lanes_with_junction) - len(lanes_no_junction)}")
    return True


def test_lane_central_curve(proxy):
    """Test getting a lane's central curve."""
    print("[TEST] Lane central curve...")
    lanes = proxy.map.lane.get_all(False, "CITY_DRIVING")
    lane_id = lanes[0]

    curve = proxy.map.lane.get_central_curve(lane_id)
    assert isinstance(curve, list), f"Expected list, got {type(curve)}"
    assert len(curve) >= 2, f"Curve should have at least 2 points, got {len(curve)}"
    assert len(curve[0]) == 2, f"Each point should be [x, y], got {curve[0]}"
    print(f"  OK - Lane '{lane_id}' has {len(curve)} center line points")
    return True


def test_lane_boundaries(proxy):
    """Test getting lane boundary curves."""
    print("[TEST] Lane boundaries...")
    lanes = proxy.map.lane.get_all(False, "CITY_DRIVING")
    lane_id = lanes[0]

    left = proxy.map.lane.get_left_boundary_curve(lane_id)
    right = proxy.map.lane.get_right_boundary_curve(lane_id)

    assert len(left) >= 2, "Left boundary too short"
    assert len(right) >= 2, "Right boundary too short"
    print(f"  OK - Left boundary: {len(left)} points, Right boundary: {len(right)} points")
    return True


def test_lane_length(proxy):
    """Test getting lane length."""
    print("[TEST] Lane length...")
    lanes = proxy.map.lane.get_all(False, "CITY_DRIVING")
    lane_id = lanes[0]

    length = proxy.map.lane.get_length(lane_id)
    assert isinstance(length, (int, float)), f"Expected number, got {type(length)}"
    assert length > 0, f"Lane length should be positive, got {length}"
    print(f"  OK - Lane '{lane_id}' length: {length:.2f} m")
    return True


def test_lane_speed_limit(proxy):
    """Test getting lane speed limit."""
    print("[TEST] Lane speed limit...")
    lanes = proxy.map.lane.get_all(False, "CITY_DRIVING")
    lane_id = lanes[0]

    speed_limit = proxy.map.lane.get_speed_limit(lane_id)
    assert speed_limit > 0, f"Speed limit should be positive, got {speed_limit}"
    print(f"  OK - Speed limit: {speed_limit:.2f} m/s ({speed_limit * 3.6:.1f} km/h)")
    return True


def test_lane_topology(proxy):
    """Test lane connectivity queries."""
    print("[TEST] Lane topology...")
    lanes = proxy.map.lane.get_all(False, "CITY_DRIVING")
    lane_id = lanes[0]

    successors = proxy.map.lane.get_successor_ids(lane_id)
    predecessors = proxy.map.lane.get_predecessor_ids(lane_id)
    left_fwd = proxy.map.lane.get_left_neighbor_forward_lane_ids(lane_id)
    right_fwd = proxy.map.lane.get_right_neighbor_forward_lane_ids(lane_id)

    print(f"  Lane: {lane_id}")
    print(f"  Successors: {successors}")
    print(f"  Predecessors: {predecessors}")
    print(f"  Left neighbors: {left_fwd}")
    print(f"  Right neighbors: {right_fwd}")
    print("  OK - Topology queries returned")
    return True


def test_find_lane_id(proxy):
    """Test finding a lane by world coordinates."""
    print("[TEST] Find lane by position...")
    lanes = proxy.map.lane.get_all(False, "CITY_DRIVING")
    lane_id = lanes[0]
    curve = proxy.map.lane.get_central_curve(lane_id)
    mid = len(curve) // 2
    x, y = curve[mid]

    result = proxy.map.find_lane_id(x, y)
    assert "lane_id" in result, f"Expected 'lane_id' in result, got {result}"
    assert "s" in result, f"Expected 's' in result, got {result}"
    print(f"  Query: ({x:.1f}, {y:.1f})")
    print(f"  Found: lane={result['lane_id']}, s={result['s']:.2f}")
    print("  OK")
    return True


def test_get_waypoint(proxy):
    """Test getting a waypoint on a lane."""
    print("[TEST] Get waypoint...")
    lanes = proxy.map.lane.get_all(False, "CITY_DRIVING")
    lane_id = lanes[0]

    wp = proxy.map.get_waypoint(lane_id, 10.0, 0.0)
    assert "x" in wp, f"Waypoint should have 'x', got {wp}"
    assert "y" in wp, f"Waypoint should have 'y', got {wp}"
    assert "heading" in wp, f"Waypoint should have 'heading', got {wp}"
    print(f"  OK - Waypoint at ({wp['x']:.1f}, {wp['y']:.1f}), heading={wp['heading']:.3f}")
    return True


def test_next_previous_waypoint(proxy):
    """Test next/previous waypoint navigation."""
    print("[TEST] Next/previous waypoints...")
    lanes = proxy.map.lane.get_all(False, "CITY_DRIVING")
    lane_id = lanes[0]

    next_wps = proxy.map.get_next_waypoint(lane_id, 5.0, 0.0, 20.0)
    prev_wps = proxy.map.get_previous_waypoint(lane_id, 20.0, 0.0, 10.0)

    assert isinstance(next_wps, list), f"Expected list, got {type(next_wps)}"
    print(f"  Next waypoints (from s=5, +20m): {len(next_wps)} results")
    print(f"  Previous waypoints (from s=20, -10m): {len(prev_wps)} results")
    print("  OK")
    return True


def test_lane_heading(proxy):
    """Test getting lane heading at a position."""
    print("[TEST] Lane heading...")
    lanes = proxy.map.lane.get_all(False, "CITY_DRIVING")
    lane_id = lanes[0]

    heading = proxy.map.get_lane_heading(lane_id, 0.0)
    assert isinstance(heading, (int, float)), f"Expected number, got {type(heading)}"
    print(f"  OK - Heading at s=0: {heading:.4f} rad")
    return True


def test_lane_direction(proxy):
    """Test getting lane direction."""
    print("[TEST] Lane direction...")
    lanes = proxy.map.lane.get_all(False, "CITY_DRIVING")
    lane_id = lanes[0]

    direction = proxy.map.get_lane_direction(lane_id)
    valid_directions = {"FORWARD", "BACKWARD", "BIDIRECTION", "UNKNOWN"}
    assert direction in valid_directions, f"Unknown direction: {direction}"
    print(f"  OK - Direction: {direction}")
    return True


def test_is_driving_lane(proxy):
    """Test is_driving_lane check."""
    print("[TEST] is_driving_lane...")
    lanes = proxy.map.lane.get_all(False, "CITY_DRIVING")
    lane_id = lanes[0]

    result = proxy.map.is_driving_lane(lane_id)
    assert result is True or result == True, f"Expected True for a CITY_DRIVING lane, got {result}"
    print(f"  OK - {lane_id} is a driving lane")
    return True


def test_lane_boundary_types(proxy):
    """Test getting lane boundary types."""
    print("[TEST] Lane boundary types...")
    lanes = proxy.map.lane.get_all(False, "CITY_DRIVING")
    lane_id = lanes[0]

    boundaries = proxy.map.get_lane_boundary_types(lane_id)
    assert "left" in boundaries, f"Expected 'left' in boundaries"
    assert "right" in boundaries, f"Expected 'right' in boundaries"
    print(f"  OK - Left: {boundaries['left']}, Right: {boundaries['right']}")
    return True


def test_render_data(proxy):
    """Test getting visualization render data."""
    print("[TEST] Render data...")
    data = proxy.map.get_render_data()
    assert "lanes" in data, "Missing 'lanes' in render data"
    assert "map_name" in data, "Missing 'map_name' in render data"
    assert len(data["lanes"]) > 0, "No lanes in render data"

    sample = data["lanes"][0]
    assert "polygon" in sample, "Lane missing 'polygon'"
    print(f"  OK - {len(data['lanes'])} lanes with render data")
    return True


def test_pathfinding(proxy):
    """Test lane pathfinding."""
    print("[TEST] Lane pathfinding...")
    lanes = proxy.map.lane.get_all(False, "CITY_DRIVING")
    if len(lanes) < 2:
        print("  SKIP - Need at least 2 lanes for pathfinding")
        return True

    # Find two lanes that are connected
    start_lane = lanes[0]
    successors = proxy.map.lane.get_successor_ids(start_lane)
    if not successors:
        print("  SKIP - Start lane has no successors")
        return True

    end_lane = successors[0]
    path = proxy.map.lane.find_path(start_lane, end_lane)
    assert isinstance(path, list), f"Expected list, got {type(path)}"
    assert len(path) >= 1, "Path should have at least 1 lane"
    print(f"  OK - Path from {start_lane} to {end_lane}: {len(path)} lanes")
    return True


def test_lane_coordinate(proxy):
    """Test Frenet to world coordinate conversion."""
    print("[TEST] Lane coordinate conversion...")
    lanes = proxy.map.lane.get_all(False, "CITY_DRIVING")
    lane_id = lanes[0]

    result = proxy.map.lane.get_coordinate(lane_id, 10.0, 0.0)
    assert result is not None, "get_coordinate returned None"
    print(f"  OK - (lane={lane_id}, s=10, l=0) -> {result}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Test map APIs")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10667)
    parser.add_argument("--map", default="borregas_ave")
    args = parser.parse_args()

    proxy = connect(f"tcp://{args.host}:{args.port}")

    tests = [
        lambda p: test_load_map(p, args.map),
        test_get_all_lanes,
        test_get_all_lanes_with_junction,
        test_lane_central_curve,
        test_lane_boundaries,
        test_lane_length,
        test_lane_speed_limit,
        test_lane_topology,
        test_find_lane_id,
        test_get_waypoint,
        test_next_previous_waypoint,
        test_lane_heading,
        test_lane_direction,
        test_is_driving_lane,
        test_lane_boundary_types,
        test_render_data,
        test_pathfinding,
        test_lane_coordinate,
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
