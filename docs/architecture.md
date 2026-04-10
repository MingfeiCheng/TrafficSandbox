# TrafficSandbox Architecture & Design

## Overview

TrafficSandbox is a deterministic, frame-based traffic simulation engine designed for autonomous driving scenario testing. It runs as a standalone server inside a Docker container, exposing two interfaces: an RPC API for programmatic control and a WebSocket-based visualization frontend.

```
                    +-----------------------------------------+
                    |         Docker Container                 |
                    |                                          |
  RPC Client  <--->| ZMQ (10667)  TrafficSandbox  Flask (18888)|<---> Browser
  (Python)         |     |             |               |      |
                   |     v             v               v      |
                   | RPCDispatcher  Simulator     SocketIO     |
                   |     |          /   \             |       |
                   |     v         v     v            v       |
                   | MapManager  Actors  Signals  Vis Push    |
                   +-----------------------------------------+
```

## Core Components

### 1. TrafficSandbox (`app.py`)

The top-level orchestrator that initializes and wires together all subsystems:

- **ZMQ RPC Server** -- Listens on port 10667 for msgpack-rpc requests
- **Flask + SocketIO Server** -- Serves the visualization UI on port 18888
- **Simulator** -- Manages the simulation loop
- **MapManager** -- Handles HD map loading and queries
- **RPCDispatcher** -- Routes incoming RPC calls to the correct handler

**Startup sequence:**
1. Create `Simulator`, `MapManager`, `RPCDispatcher`
2. Register all RPC methods via `register_module_api()` (auto-discovers `@sandbox_api` methods)
3. Start the ZMQ RPC server in a background thread
4. Start the Flask/SocketIO server (blocking, with eventlet)
5. Launch the visualization data push thread (50ms interval)

### 2. Simulator (`simulator.py`)

The simulation engine that drives the world forward in discrete time steps.

**Key responsibilities:**
- Maintains collections of `actors` (dict) and `signals` (dict)
- Runs a fixed-timestep loop at the target FPS (default 100)
- Each tick: updates all actors/signals, increments the frame counter

**Simulation states:**
- `waiting` -- Actors can be created/configured, but the tick loop does not advance actor physics
- `running` -- The tick loop is active; actors update position/velocity each frame

**Thread model:**
- The simulation loop runs in its own daemon thread (`start(blocking=False)`)
- Thread-safe access to actors/signals via the RPC server thread

### 3. Actor System

#### Hierarchy

```
Actor (base.py)
├── VehicleActor (vehicle/base.py)
│   ├── LincolnMKZ           -- Kinematic steering model
│   ├── PerfectLincolnMKZ     -- Direct heading control
│   ├── LincolnMKZLGSVL       -- LGSVL-sized variant
│   ├── PerfectLincolnMKZLGSVL
│   ├── Bicycle               -- Smaller vehicle model
│   └── PerfectBicycle
├── WalkerActor (walker/base.py)
│   └── PedestrianNormal      -- Point-mass dynamics
├── StaticActor (static/base.py)
│   └── TrafficCone            -- Immovable obstacle
└── TrafficLight (signal/traffic_light.py)
    └── State machine: green <-> yellow <-> red
```

#### Vehicle Physics Model

Standard vehicles use a **bicycle kinematic model**:

```
Parameters:
  wheelbase      = 2.8448 m
  steer_ratio    = 16.0
  max_steer_angle = 8.20 rad
  max_accel      = 2.0 m/s^2
  max_decel      = -6.0 m/s^2

Per-tick update:
  1. acceleration = throttle * max_accel + brake * max_decel
  2. speed += acceleration * dt
  3. steer_angle = steer * max_steer_angle / steer_ratio
  4. angular_velocity = speed * tan(steer_angle) / wheelbase
  5. heading += angular_velocity * dt
  6. x += speed * cos(heading) * dt
  7. y += speed * sin(heading) * dt
```

**Perfect vehicles** bypass step 3-5: they directly set `heading = target_heading` each tick. This is useful for ego vehicles where you want exact waypoint following without kinematic lag.

#### Walker Physics

Simpler point-mass model:
```
Per-tick update:
  1. speed += acceleration * dt  (clamped to [-10, 10] m/s^2)
  2. heading = target_heading     (instant heading change)
  3. x += speed * cos(heading) * dt
  4. y += speed * sin(heading) * dt
```

#### Registry Pattern

All actor types are registered in a global `ACTOR_REGISTRY` singleton. Each actor subclass declares its type string (e.g., `"vehicle.lincoln.mkz"`) and is auto-discovered at import time via `common/utils.py`.

```python
# In lincoln_mkz.py
@ACTOR_REGISTRY.register("vehicle.lincoln.mkz")
class LincolnMKZ(VehicleActor):
    ...
```

To create an actor, the simulator looks up the type in the registry:
```python
actor_cls = ACTOR_REGISTRY.get(actor_type)
actor = actor_cls(actor_id, x, y, z, heading)
```

### 4. Map Toolkit (`map_toolkit/`)

Manages Apollo HD map data for lane-level queries.

#### Components

| Module | Responsibility |
|--------|---------------|
| `MapManager` | Top-level map interface; delegates to sub-managers |
| `RoadLaneManager` | Lane geometry, topology, pathfinding |
| `JunctionManager` | Junction boundaries and connected lanes |
| `CrosswalkManager` | Crosswalk polygons |
| `StopSignManager` | Stop sign locations and associated lanes |
| `TrafficLightManager` | Traffic light signal-to-lane mappings |

#### Data Flow

```
map.pickle (serialized Apollo protobuf)
    │
    v
MapManager.load_map()
    │
    ├── RoadLaneManager  ── builds NetworkX DiGraph (lane connectivity)
    │                     ── builds R-tree spatial index (lane lookup)
    │
    ├── JunctionManager
    ├── CrosswalkManager
    ├── StopSignManager
    └── TrafficLightManager
```

#### Lane Coordinate System

Each lane uses a **Frenet coordinate system**:
- **s** (longitudinal): distance along the lane's center line from the start
- **l** (lateral): perpendicular offset from the center line (positive = left)

Key operations:
- `find_lane_id(x, y)` -- World coordinates -> (lane_id, s) via R-tree
- `get_coordinate(lane_id, s, l)` -- Frenet -> world coordinates (x, y, heading)
- `find_path(start_lane, end_lane)` -- Shortest path via NetworkX Dijkstra

### 5. RPC System

#### `@sandbox_api` Decorator

The `@sandbox_api` decorator in `common/rpc_utils.py` wraps methods for RPC exposure:

```python
@sandbox_api("reset")
def reset(self):
    self.actors.clear()
    self.signals.clear()
```

**What the decorator does:**
1. Marks the method for auto-registration
2. Wraps the return value in `{"status": "ok", "data": result}`
3. Catches exceptions and returns `{"status": "error", "message": ..., "traceback": ...}`

#### RPC Namespacing

Methods are namespaced by their object's position in the hierarchy:

```
TrafficSandbox
├── .simulator        -> sim.*
│   └── .reset()      -> sim.reset
├── .map_manager      -> map.*
│   ├── .get_waypoint() -> map.get_waypoint
│   └── .road_lane    -> map.lane.*
│       └── .get_all() -> map.lane.get_all
├── .load_map()       -> load_map
└── .shutdown()       -> shutdown
```

#### Transport

- **Protocol**: MessagePack-RPC (compact binary serialization)
- **Transport**: ZMQ REQ/REP socket pair
- **Library**: `tinyrpc` with `MSGPACKRPCProtocol`

### 6. Visualization Frontend

#### Architecture

```
Flask Server (port 18888)
    │
    ├── GET /  -> templates/index.html
    │
    └── SocketIO events:
        ├── map_loading_start  (server -> client)
        ├── init_map           (server -> client, map geometry data)
        ├── map_loading_done   (server -> client)
        ├── traffic_update     (server -> client, 50ms interval)
        └── map_loading_error  (server -> client)
```

#### Canvas Layers

Three stacked `<canvas>` elements with z-index ordering:

| Layer | Z-Index | Content | Redraw Frequency |
|-------|---------|---------|-----------------|
| Map | 1 | Lane polygons, lane boundaries | On map load / view change |
| Traffic Lights | 2 | Stop lines colored by signal state | Every traffic_update (50ms) |
| Actors | 3 | Actor polygons with ID/speed labels | Every traffic_update (50ms) |

#### View Transforms

All three canvases share a common transform pipeline:
```
Canvas center -> translate(offsetX, offsetY) -> rotate(angle) -> scale(s) -> translate(-mapCenterX, -mapCenterY)
```

The map canvas uses this full pipeline; actor/traffic light canvases use a simplified version for coordinate normalization.

#### Client-Side Caching

Map data is cached in **IndexedDB** to avoid re-downloading on page refresh:
- On `init_map`: store map data keyed by `map_name`
- On page load: check `localStorage.lastMapName`, restore from IndexedDB
- Cache can be cleared via `clearMapCache()` in console

## Data Flow Summary

### Simulation Tick (100 FPS)

```
Simulator._loop()
  └── for each frame:
      ├── actor.tick(dt) for all actors  (update physics)
      ├── signal.tick(dt) for all signals (update timers)
      └── timer.tick() (increment frame counter)
```

### Visualization Push (20 FPS / 50ms)

```
TrafficSandbox._traffic_dataflow()
  └── every 50ms:
      ├── simulator.get_snapshot()
      └── socketio.emit("traffic_update", snapshot)
```

### RPC Request Flow

```
Client call  ->  ZMQ transport  ->  RPCDispatcher
                                        │
                                  lazy_resolver(method_name)
                                        │
                                  @sandbox_api wrapper
                                        │
                                  actual method execution
                                        │
                                  {status: ok/error, data/message}
                                        │
                                  ZMQ transport  ->  Client response
```

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Configurable ports (`--rpc-port`, `--vis-port`) | Allows running multiple instances or avoiding conflicts with other services |
| ZMQ + msgpack-rpc | Low-latency binary RPC; avoids HTTP overhead for tight simulation loops |
| Pickle-based map files | Fast deserialization of complex Apollo protobuf structures |
| Registry pattern for actors | Enables dynamic type discovery; new actors only need a decorated class |
| Separate perfect/normal variants | Allows choosing kinematic realism vs. exact trajectory following per actor |
| Multi-canvas rendering | Separates redraw frequencies (map is static, actors update at 20fps) |
| IndexedDB map caching | Large map data (MB-sized) is expensive to re-transmit on every page load |
| Fixed-timestep simulation | Deterministic results regardless of wall-clock performance |
