"""
Frontend debug test script.

Creates a realistic traffic scenario with multiple actor types, moving vehicles,
pedestrians, and changing traffic lights so you can visually verify the frontend
rendering at http://localhost:8888.

Usage:
    python tests/test_frontend_debug.py [--host HOST] [--port PORT] [--map MAP] [--duration SECONDS]
"""

import argparse
import math
import time
import random
from rpc_client import connect


def setup_scenario(proxy, map_name):
    """Load map and get available lanes for spawning."""
    print(f"[Setup] Loading map: {map_name}")
    proxy.load_map(map_name)
    print(f"[Setup] Map loaded: {proxy.map.get_current_map()}")

    proxy.sim.reset()

    lanes = proxy.map.lane.get_all(False, "CITY_DRIVING")
    print(f"[Setup] Found {len(lanes)} driving lanes")
    return lanes


def get_lane_spawn_point(proxy, lane_id, s_ratio=0.5):
    """Get a spawn point on a lane at a given ratio along its length."""
    length = proxy.map.lane.get_length(lane_id)
    s = length * s_ratio
    result = proxy.map.lane.get_coordinate(lane_id, s, 0.0)
    if isinstance(result, (list, tuple)) and len(result) == 3:
        x, y, heading = result
    else:
        curve = proxy.map.lane.get_central_curve(lane_id)
        idx = int(len(curve) * s_ratio)
        idx = max(0, min(idx, len(curve) - 1))
        x, y = curve[idx]
        heading = proxy.map.get_lane_heading(lane_id, s)
    return x, y, heading


def create_vehicles(proxy, lanes, count=4):
    """Create vehicles on different lanes."""
    created = []
    lane_list = list(lanes)
    used_lanes = random.sample(lane_list, min(count, len(lane_list)))

    vehicle_types = [
        "vehicle.lincoln.mkz",
        "vehicle.lincoln.mkz.perfect",
        "vehicle.lincoln.mkz_lgsvl",
        "vehicle.bicycle.normal",
    ]

    for i, lane_id in enumerate(used_lanes):
        actor_id = f"vehicle_{i}"
        actor_type = vehicle_types[i % len(vehicle_types)]
        try:
            x, y, heading = get_lane_spawn_point(proxy, lane_id, 0.2)
            proxy.sim.create_actor({
                "actor_id": actor_id,
                "actor_type": actor_type,
                "x": x, "y": y, "z": 0.0,
                "heading": heading
            })
            proxy.sim.set_actor_status(actor_id, "ready")
            created.append({
                "id": actor_id,
                "type": actor_type,
                "lane": lane_id,
                "heading": heading,
                "is_perfect": "perfect" in actor_type,
                "is_bicycle": "bicycle" in actor_type,
            })
            print(f"  Created {actor_type} '{actor_id}' on lane {lane_id}")
        except Exception as e:
            print(f"  Failed to create vehicle on lane {lane_id}: {e}")

    return created


def create_pedestrians(proxy, lanes, count=2):
    """Create pedestrians near some lanes."""
    created = []
    lane_list = list(lanes)
    used_lanes = random.sample(lane_list, min(count, len(lane_list)))

    for i, lane_id in enumerate(used_lanes):
        actor_id = f"walker_{i}"
        try:
            x, y, heading = get_lane_spawn_point(proxy, lane_id, 0.3)
            # Offset pedestrian slightly from lane center
            x += 3.0 * math.cos(heading + math.pi / 2)
            y += 3.0 * math.sin(heading + math.pi / 2)

            proxy.sim.create_actor({
                "actor_id": actor_id,
                "actor_type": "walker.pedestrian.normal",
                "x": x, "y": y, "z": 0.0,
                "heading": heading + math.pi / 2  # walk perpendicular to road
            })
            proxy.sim.set_actor_status(actor_id, "ready")
            created.append({
                "id": actor_id,
                "heading": heading + math.pi / 2,
            })
            print(f"  Created pedestrian '{actor_id}'")
        except Exception as e:
            print(f"  Failed to create pedestrian: {e}")

    return created


def create_static_objects(proxy, lanes, count=3):
    """Create traffic cones along a lane."""
    created = []
    lane_id = random.choice(list(lanes))

    for i in range(count):
        actor_id = f"cone_{i}"
        try:
            x, y, heading = get_lane_spawn_point(proxy, lane_id, 0.5 + i * 0.05)
            # Place cones slightly offset from center
            x += 1.5 * math.cos(heading + math.pi / 2)
            y += 1.5 * math.sin(heading + math.pi / 2)

            proxy.sim.create_actor({
                "actor_id": actor_id,
                "actor_type": "static.traffic_cone",
                "x": x, "y": y, "z": 0.0,
                "heading": 0.0
            })
            proxy.sim.set_actor_status(actor_id, "ready")
            created.append(actor_id)
            print(f"  Created traffic cone '{actor_id}'")
        except Exception as e:
            print(f"  Failed to create cone: {e}")

    return created


def create_traffic_lights(proxy, count=3):
    """Create traffic lights using real map signal IDs so stop lines render."""
    states = ["green", "red", "yellow"]
    created = []

    # Try to use real map traffic light IDs (they have stop_line geometry)
    try:
        map_tl_ids = proxy.map.traffic_light.get_all()
        if isinstance(map_tl_ids, list) and len(map_tl_ids) > 0:
            use_ids = map_tl_ids[:count]
            print(f"  Using {len(use_ids)} map traffic light IDs: {use_ids}")
        else:
            use_ids = [f"tl_{i}" for i in range(count)]
    except Exception:
        use_ids = [f"tl_{i}" for i in range(count)]

    for i, signal_id in enumerate(use_ids):
        state = states[i % len(states)]
        try:
            proxy.sim.create_signal({
                "signal_id": signal_id,
                "signal_type": "signal.traffic_light",
                "signal_state": state
            })
            created.append({"id": signal_id, "state": state})
            print(f"  Created traffic light '{signal_id}' (state={state})")
        except Exception as e:
            print(f"  Failed to create traffic light '{signal_id}': {e}")

    return created


def run_simulation(proxy, vehicles, walkers, traffic_lights, duration):
    """Run the simulation with periodic control commands."""
    print(f"\n[Simulation] Starting {duration}s simulation loop...")
    print(f"  Open http://localhost:18888 to see the visualization\n")

    proxy.sim.start_scenario()

    tl_states = ["green", "red", "yellow"]
    tl_cycle_interval = 5.0  # seconds per state change
    start_time = time.time()
    last_tl_change = start_time
    tl_state_idx = 0

    frame_count = 0
    try:
        while time.time() - start_time < duration:
            elapsed = time.time() - start_time

            # Control vehicles
            for v in vehicles:
                if v["is_perfect"]:
                    proxy.sim.apply_vehicle_control(v["id"], {
                        "acceleration": 1.5,
                        "heading": v["heading"],
                        "throttle": 0.0, "brake": 0.0, "steer": 0.0, "reverse": False
                    })
                elif v["is_bicycle"]:
                    proxy.sim.apply_vehicle_control(v["id"], {
                        "throttle": 0.2,
                        "steer": 0.0,
                        "brake": 0.0,
                        "reverse": False
                    })
                else:
                    # Vary throttle with a sine wave for natural-looking driving
                    throttle = 0.3 + 0.2 * math.sin(elapsed * 0.5)
                    proxy.sim.apply_vehicle_control(v["id"], {
                        "throttle": throttle,
                        "steer": 0.0,
                        "brake": 0.0,
                        "reverse": False
                    })

            # Control walkers
            for w in walkers:
                proxy.sim.apply_walker_action(w["id"], {
                    "acceleration": 0.8,
                    "heading": w["heading"]
                })

            # Cycle traffic light states
            if time.time() - last_tl_change > tl_cycle_interval:
                tl_state_idx = (tl_state_idx + 1) % len(tl_states)
                new_state = tl_states[tl_state_idx]
                for tl in traffic_lights:
                    proxy.sim.set_signal_state(tl["id"], new_state)
                last_tl_change = time.time()
                print(f"  [{elapsed:.1f}s] Traffic lights -> {new_state}")

            # Print status every 5 seconds
            if frame_count % 500 == 0:
                snapshot = proxy.sim.get_snapshot()
                print(f"  [{elapsed:.1f}s] frame={snapshot.get('frame', '?')}, "
                      f"game_time={snapshot.get('game_time', 0):.2f}s, "
                      f"actors={len(snapshot.get('actors', []))}, "
                      f"signals={len(snapshot.get('traffic_lights', []))}")

            frame_count += 1
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n[Simulation] Interrupted by user")

    proxy.sim.stop_scenario()
    print(f"\n[Simulation] Stopped after {time.time() - start_time:.1f}s, {frame_count} control frames")


def main():
    parser = argparse.ArgumentParser(description="Frontend debug test")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10667)
    parser.add_argument("--map", default="borregas_ave")
    parser.add_argument("--duration", type=float, default=60.0, help="Simulation duration in seconds")
    args = parser.parse_args()

    proxy = connect(f"tcp://{args.host}:{args.port}")

    # Setup
    lanes = setup_scenario(proxy, args.map)

    print("\n[Creating actors]")
    vehicles = create_vehicles(proxy, lanes, count=4)
    walkers = create_pedestrians(proxy, lanes, count=2)
    cones = create_static_objects(proxy, lanes, count=3)
    traffic_lights = create_traffic_lights(proxy, count=3)

    # Print summary
    print(f"\n[Summary]")
    print(f"  Vehicles:       {len(vehicles)}")
    print(f"  Pedestrians:    {len(walkers)}")
    print(f"  Traffic cones:  {len(cones)}")
    print(f"  Traffic lights: {len(traffic_lights)}")

    # Run
    run_simulation(proxy, vehicles, walkers, traffic_lights, args.duration)

    # Cleanup
    print("\n[Cleanup] Resetting simulation...")
    proxy.sim.reset()
    print("[Done]")


if __name__ == "__main__":
    main()
