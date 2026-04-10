# TrafficSandbox

A lightweight traffic simulation sandbox that runs inside a Docker container and exposes its functionality via MessagePack-RPC over ZMQ.

## Architecture

```
+---------------------------------------------------+
|  Docker Container (drivora/sandbox:latest)         |
|                                                    |
|  TrafficSandbox (app.py)                           |
|  ├── Simulator        (actor tick loop)            |
|  ├── MapManager       (HD map queries)             |
|  ├── RPC Server       (ZMQ, port 10667)            |
|  └── Vis Server       (Flask+SocketIO, port 8888)  |
+---------------------------------------------------+
         ▲
         │  TCP / ZMQ (msgpack-rpc)
         ▼
+---------------------------------------------------+
|  Host / Client                                     |
|  SandboxOperator  (scenario_runner/sandbox_operator)|
|  ├── operator.sim.*       → Simulator RPC          |
|  ├── operator.map.*       → MapManager RPC         |
|  └── operator.load_map()  → Root RPC               |
+---------------------------------------------------+
```

## Quick Start

### 1. Build the Docker image

```bash
cd Apollo/TrafficSandbox
docker build -t drivora/sandbox:latest .
```

### 2. Start the container

```bash
docker run --name sandbox_dev --rm -d \
    drivora/sandbox:latest \
    bash -c "python /app/app.py --fps 100"
```

### 3. Connect from Python (client side)

```python
from scenario_runner.sandbox_operator import SandboxOperator

operator = SandboxOperator(container_name="sandbox_dev")

# Load a map
operator.load_map("san_mateo")

# Create an actor
operator.sim.create_actor({
    "actor_id": "ego_1",
    "actor_type": "vehicle.lincoln.mkz",
    "x": 559700.0, "y": 4157850.0, "z": 0.0,
    "heading": 1.57
})

# Start simulation
operator.sim.start_scenario()

# Get world snapshot
snapshot = operator.sim.get_snapshot()

# Query map
waypoint = operator.map.get_waypoint("lane_1", s=10.0, l=0.0)

# Cleanup
operator.close()
```

## RPC API Reference

All RPC calls return `{"status": "ok", "data": <result>}` on success or `{"status": "error", "message": "...", "traceback": "..."}` on failure.

### Root APIs

| Method | Args | Description |
|--------|------|-------------|
| `load_map(map_name)` | `str` | Load HD map data and notify frontend |
| `set_timeout(timeout)` | `float` | Set map loading timeout (seconds) |
| `shutdown()` | - | Gracefully stop all components |

### Simulator APIs (`sim.*`)

| Method | Args | Description |
|--------|------|-------------|
| `sim.reset()` | - | Clear all actors/signals, reset timer |
| `sim.start_scenario()` | - | Start the simulation tick loop |
| `sim.stop_scenario()` | - | Pause the simulation |
| `sim.get_time()` | - | Get frame count, game time, real FPS |
| `sim.get_snapshot()` | - | Get full world state (actors + signals) |
| `sim.get_actor(actor_id)` | `str` | Get single actor state |
| `sim.get_signal(signal_id)` | `str` | Get single signal state |
| `sim.get_actor_blueprint(actor_type)` | `str` | Get actor schema |
| `sim.get_scenario_status()` | - | Returns `"running"` or `"waiting"` |
| `sim.create_actor(config)` | `dict` | Spawn actor (see config below) |
| `sim.create_signal(config)` | `dict` | Spawn traffic signal |
| `sim.remove_actor(actor_id)` | `str` | Despawn actor |
| `sim.remove_signal(signal_id)` | `str` | Despawn signal |
| `sim.set_actor_status(actor_id, status)` | `str, str` | Set actor readiness |
| `sim.set_static_location(actor_id, location)` | `str, dict` | Teleport actor |
| `sim.set_signal_state(signal_id, state)` | `str, str` | Update signal |
| `sim.apply_vehicle_control(actor_id, control)` | `str, dict` | Send vehicle control |
| `sim.apply_walker_action(actor_id, action)` | `str, dict` | Send walker control |

**Actor config:**
```python
{
    "actor_id": "ego_1",
    "actor_type": "vehicle.lincoln.mkz",  # see Actor Types below
    "x": 559700.0,
    "y": 4157850.0,
    "z": 0.0,
    "heading": 1.57  # radians
}
```

**Vehicle control:**
```python
{"throttle": 0.5, "steer": 0.0, "brake": 0.0, "reverse": False}
```

**Walker control:**
```python
{"acceleration": 1.0, "heading": 0.0}
```

### Map APIs (`map.*`)

| Method | Args | Returns | Description |
|--------|------|---------|-------------|
| `map.get_current_map()` | - | `str` | Current map name |
| `map.get_render_data()` | - | `dict` | Lanes + stop signs for visualization |
| `map.get_waypoint(lane_id, s, l)` | `str, float, float` | `Waypoint` | Waypoint at (s, l) on lane |
| `map.get_next_waypoint(lane_id, s, l, distance)` | `str, float, float, float` | `list[Waypoint]` | Next waypoint(s) ahead |
| `map.get_previous_waypoint(lane_id, s, l, distance)` | `str, float, float, float` | `list[Waypoint]` | Previous waypoint(s) behind |
| `map.find_lane_id(x, y)` | `float, float` | `{"lane_id": str, "s": float}` | Find lane at world position |
| `map.get_speed_limit(lane_id)` | `str` | `float` | Lane speed limit (m/s) |
| `map.get_lane_heading(lane_id, s)` | `str, float` | `float` | Lane heading (radians) at s |
| `map.get_lane_direction(lane_id)` | `str` | `str` | `FORWARD` / `BACKWARD` / `BIDIRECTION` / `UNKNOWN` |
| `map.is_driving_lane(lane_id)` | `str` | `bool` | True if `CITY_DRIVING` type |

**Waypoint structure:**
```python
{
    "lane_id": "lane_123",
    "is_junction": False,
    "s": 15.0,
    "l": 0.0,
    "x": 559710.5,
    "y": 4157860.3,
    "heading": 1.57,
    "speed_limit": 11.11
}
```

## Actor Types

Registered actor types (used in `actor_type` field):

| Type | Description |
|------|-------------|
| `vehicle.lincoln.mkz` | Lincoln MKZ sedan |
| `vehicle.lincoln.mkz.perfect` | Lincoln MKZ (perfect tracking) |
| `vehicle.lincoln.mkz_lgsvl` | Lincoln MKZ (LGSVL variant) |
| `vehicle.lincoln.mkz_lgsvl.perfect` | Lincoln MKZ LGSVL (perfect tracking) |
| `vehicle.bicycle.normal` | Bicycle |
| `vehicle.bicycle.normal.perfect` | Bicycle (perfect tracking) |
| `walker.pedestrian.normal` | Pedestrian |
| `static.traffic_cone` | Traffic cone |
| `signal.traffic_light` | Traffic light |

## Snapshot Structure

The `sim.get_snapshot()` return value:

```python
{
    "time": {
        "frame": 1234,
        "game_time": 12.34,
        "real_time_elapsed": 15.2,
        "real_fps": 98.5,
        "target_fps": 100.0,
        "server_time": 1711900000.0
    },
    "scenario_running": True,
    "actors": {
        "ego_1": {
            "location": {"x": ..., "y": ..., "z": ..., "yaw": ..., ...},
            "speed": 5.2,
            "polygon": [[x,y], [x,y], ...],
            ...
        },
        ...
    },
    "signals": {
        "tl_001": { ... },
        ...
    }
}
```

## Adding Custom @sandbox_api Methods

To expose a new RPC endpoint, use the `@sandbox_api` decorator on any method
within `TrafficSandbox`, `Simulator`, `MapManager`, or their sub-objects:

```python
from common.rpc_utils import sandbox_api

class MyManager:
    @sandbox_api("my_custom_query")
    def my_custom_query(self, param: str) -> dict:
        return {"result": param}
```

The method will be auto-registered during startup via `register_module_api()`.
The RPC name is determined by the object's position in the hierarchy
(e.g., `map.lane.my_custom_query`).

## Directory Structure

```
TrafficSandbox/
├── app.py                  # Server entry point + TrafficSandbox class
├── simulator.py            # Simulation tick loop + actor management
├── config.py               # Global config (ports, FPS, logging)
├── Dockerfile              # Container image definition
├── common/
│   ├── rpc_utils.py        # @sandbox_api decorator + RPC registration
│   ├── data_structure.py   # Location, Waypoint, BoundingBox dataclasses
│   ├── timer.py            # Frame-based simulation timer
│   └── utils.py            # Module discovery for actor registration
├── map_toolkit/
│   ├── map_manager.py      # MapManager (waypoint + lane queries)
│   ├── road_lane.py        # RoadLaneManager (lane geometry + topology)
│   ├── waypoint.py         # Waypoint dataclass
│   ├── junction.py         # Junction management
│   ├── crosswalk.py        # Crosswalk management
│   ├── stop_sign.py        # Stop sign management
│   ├── traffic_light.py    # Traffic light management
│   └── data/               # Pre-built map pickle files
├── actor/
│   ├── vehicle/            # Vehicle actor implementations
│   ├── walker/             # Pedestrian actor implementations
│   ├── static/             # Static object implementations
│   ├── signal/             # Traffic signal implementations
│   └── control/            # Control command dataclasses
├── registry/               # Actor type registration system
├── templates/              # Flask HTML templates (visualization)
└── static/                 # Frontend CSS/JS (visualization)
```

## Network Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 10667 | TCP (ZMQ msgpack-rpc) | RPC server |
| 8888 | HTTP + WebSocket | Visualization frontend |
