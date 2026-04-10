# TrafficSandbox API Reference

All RPC methods return a response envelope:

```python
# Success
{"status": "ok", "data": <result>}

# Error
{"status": "error", "message": "<error message>", "traceback": "<full traceback>"}
```

---

## Root APIs

### `load_map(map_name)`

Load an HD map by name. Notifies the visualization frontend to update.

| Parameter | Type | Description |
|-----------|------|-------------|
| `map_name` | `str` | Map directory name (e.g., `"san_mateo"`, `"borregas_ave"`) |

**Returns:** Map loading status

---

### `set_timeout(timeout)`

Set the timeout for map loading operations.

| Parameter | Type | Description |
|-----------|------|-------------|
| `timeout` | `float` | Timeout in seconds |

---

### `shutdown()`

Gracefully stop all server components (RPC, Flask, simulator).

---

## Simulator APIs (`sim.*`)

### `sim.reset()`

Clear all actors and signals, reset the simulation timer to frame 0.

**Returns:** `None`

---

### `sim.start_scenario()`

Start the simulation tick loop. All actors with `"ready"` status will begin updating.

**Returns:** `None`

---

### `sim.stop_scenario()`

Pause the simulation tick loop. Actors retain their current state.

**Returns:** `None`

---

### `sim.get_scenario_status()`

**Returns:** `"running"` | `"waiting"`

---

### `sim.get_time()`

Get current simulation timing information.

**Returns:**
```python
{
    "frame": 1234,              # Current frame number
    "game_time": 12.34,         # Simulation time in seconds
    "real_time_elapsed": 15.2,  # Wall-clock time since start
    "real_fps": 98.5,           # Actual frames per second
    "target_fps": 100.0,        # Configured target FPS
    "server_time": 1711900000.0 # Server unix timestamp
}
```

---

### `sim.get_snapshot()`

Get the complete world state.

**Returns:**
```python
{
    "time": { ... },           # Same as sim.get_time()
    "scenario_running": true,
    "actors": {
        "actor_id": {
            "id": "actor_id",
            "category": "vehicle.lincoln.mkz",
            "role": "npc",     # or "ads"
            "status": "ready",
            "location": {
                "x": 587078.0, "y": 4141416.0, "z": 0.0,
                "pitch": 0.0, "yaw": 1.57, "roll": 0.0
            },
            "speed": 5.2,
            "acceleration": 0.5,
            "bounding_box": {"length": 4.93, "width": 2.11, "height": 1.48},
            "polygon": [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        },
        ...
    },
    "signals": {
        "signal_id": {
            "id": "signal_id",
            "state": "green",
            "state_time": 5.2  # seconds in current state
        },
        ...
    }
}
```

---

### `sim.get_actor(actor_id)`

Get the state of a single actor.

| Parameter | Type | Description |
|-----------|------|-------------|
| `actor_id` | `str` | Actor identifier |

**Returns:** Actor state dict (same format as in snapshot)

---

### `sim.get_signal(signal_id)`

Get the state of a single signal.

| Parameter | Type | Description |
|-----------|------|-------------|
| `signal_id` | `str` | Signal identifier |

**Returns:** Signal state dict (same format as in snapshot)

---

### `sim.get_actor_blueprint(actor_type)`

Get the schema/blueprint for an actor type.

| Parameter | Type | Description |
|-----------|------|-------------|
| `actor_type` | `str` | Actor type ID (e.g., `"vehicle.lincoln.mkz"`) |

**Returns:** Actor type schema including dimensions and default parameters

---

### `sim.create_actor(config)`

Spawn a new actor in the simulation.

| Parameter | Type | Description |
|-----------|------|-------------|
| `config` | `dict` | Actor configuration |

**Config format:**
```python
{
    "actor_id": "npc_1",              # Unique identifier
    "actor_type": "vehicle.lincoln.mkz",  # Registered type ID
    "x": 587078.0,                    # World x coordinate
    "y": 4141416.0,                   # World y coordinate
    "z": 0.0,                         # World z coordinate
    "heading": 1.57                   # Heading in radians
}
```

**Returns:**
```python
{
    "actor_id": "npc_1",
    "actor_type": "vehicle.lincoln.mkz",
    "x": 587078.0,
    "y": 4141416.0,
    "z": 0.0,
    "heading": 1.57
}
```

---

### `sim.create_signal(config)`

Spawn a new traffic signal.

| Parameter | Type | Description |
|-----------|------|-------------|
| `config` | `dict` | Signal configuration |

**Config format:**
```python
{
    "signal_id": "tl_1",
    "signal_type": "signal.traffic_light",
    "signal_state": "green"  # "green", "red", "yellow"
}
```

**Returns:**
```python
{
    "signal_id": "tl_1",
    "signal_type": "signal.traffic_light",
    "signal_state": "green"
}
```

---

### `sim.remove_actor(actor_id)`

Remove an actor from the simulation.

| Parameter | Type | Description |
|-----------|------|-------------|
| `actor_id` | `str` | Actor to remove |

---

### `sim.remove_signal(signal_id)`

Remove a signal from the simulation.

| Parameter | Type | Description |
|-----------|------|-------------|
| `signal_id` | `str` | Signal to remove |

---

### `sim.set_actor_status(actor_id, status)`

Set an actor's readiness status. Actors must be set to `"ready"` before they will be updated by the simulation loop.

| Parameter | Type | Description |
|-----------|------|-------------|
| `actor_id` | `str` | Actor identifier |
| `status` | `str` | `"ready"` or `"not_ready"` |

---

### `sim.set_static_location(actor_id, location)`

Teleport a static actor to a new position.

| Parameter | Type | Description |
|-----------|------|-------------|
| `actor_id` | `str` | Static actor identifier |
| `location` | `dict` | `{x, y, z, pitch, yaw, roll}` |

---

### `sim.set_signal_state(signal_id, state)`

Update a traffic signal's state.

| Parameter | Type | Description |
|-----------|------|-------------|
| `signal_id` | `str` | Signal identifier |
| `state` | `str` | `"green"`, `"red"`, or `"yellow"` |

---

### `sim.apply_vehicle_control(actor_id, control)`

Send a control command to a vehicle actor.

| Parameter | Type | Description |
|-----------|------|-------------|
| `actor_id` | `str` | Vehicle actor identifier |
| `control` | `dict` | Control command |

**Control format (standard vehicles):**
```python
{
    "throttle": 0.5,   # [0.0, 1.0] - acceleration input
    "steer": 0.0,      # [-1.0, 1.0] - steering input (left/right)
    "brake": 0.0,      # [0.0, 1.0] - braking input
    "reverse": false   # bool - drive in reverse
}
```

**Control format (perfect vehicles):**
```python
{
    "acceleration": 2.0,  # m/s^2 - direct acceleration
    "heading": 1.57,      # radians - target heading (applied instantly)
    "throttle": 0.0,      # ignored for perfect vehicles
    "brake": 0.0,         # ignored for perfect vehicles
    "steer": 0.0,         # ignored for perfect vehicles
    "reverse": false      # ignored for perfect vehicles
}
```

---

### `sim.apply_walker_action(actor_id, action)`

Send a control command to a walker actor.

| Parameter | Type | Description |
|-----------|------|-------------|
| `actor_id` | `str` | Walker actor identifier |
| `action` | `dict` | Walker action |

**Action format:**
```python
{
    "acceleration": 1.5,  # [-10.0, 10.0] m/s^2
    "heading": 0.0        # radians - target heading
}
```

---

## Map APIs (`map.*`)

### `map.get_current_map()`

**Returns:** `str` -- Current map name

---

### `map.get_render_data()`

Get map geometry data for visualization rendering.

**Returns:**
```python
{
    "map_name": "san_mateo",
    "lanes": [
        {
            "polygon": [[x,y], ...],
            "left_boundary": [[x,y], ...],
            "right_boundary": [[x,y], ...],
            "left_boundary_type": "SOLID_WHITE",
            "right_boundary_type": "DOTTED_WHITE"
        },
        ...
    ],
    "stop_signs": [ ... ]
}
```

---

### `map.get_waypoint(lane_id, s, l)`

Get a waypoint at a specific Frenet coordinate on a lane.

| Parameter | Type | Description |
|-----------|------|-------------|
| `lane_id` | `str` | Lane identifier |
| `s` | `float` | Longitudinal position (meters from lane start) |
| `l` | `float` | Lateral offset (meters from center, positive = left) |

**Returns:**
```python
{
    "lane_id": "lane_123",
    "is_junction": false,
    "s": 15.0,
    "l": 0.0,
    "x": 587078.5,
    "y": 4141420.3,
    "heading": 1.57,
    "speed_limit": 11.11
}
```

---

### `map.get_next_waypoint(lane_id, s, l, distance)`

Get the next waypoint(s) ahead of the current position by a given distance. May return multiple waypoints at lane splits.

| Parameter | Type | Description |
|-----------|------|-------------|
| `lane_id` | `str` | Current lane |
| `s` | `float` | Current longitudinal position |
| `l` | `float` | Current lateral offset |
| `distance` | `float` | Look-ahead distance in meters |

**Returns:** `list[Waypoint]`

---

### `map.get_previous_waypoint(lane_id, s, l, distance)`

Get the previous waypoint(s) behind the current position.

| Parameter | Type | Description |
|-----------|------|-------------|
| `lane_id` | `str` | Current lane |
| `s` | `float` | Current longitudinal position |
| `l` | `float` | Current lateral offset |
| `distance` | `float` | Look-behind distance in meters |

**Returns:** `list[Waypoint]`

---

### `map.find_lane_id(x, y)`

Find the nearest lane at a world coordinate using the spatial index.

| Parameter | Type | Description |
|-----------|------|-------------|
| `x` | `float` | World x coordinate |
| `y` | `float` | World y coordinate |

**Returns:** `{"lane_id": "lane_123", "s": 10.5}`

---

### `map.get_speed_limit(lane_id)`

| Parameter | Type | Description |
|-----------|------|-------------|
| `lane_id` | `str` | Lane identifier |

**Returns:** `float` -- Speed limit in m/s

---

### `map.get_lane_heading(lane_id, s)`

| Parameter | Type | Description |
|-----------|------|-------------|
| `lane_id` | `str` | Lane identifier |
| `s` | `float` | Longitudinal position |

**Returns:** `float` -- Heading in radians

---

### `map.get_lane_direction(lane_id)`

| Parameter | Type | Description |
|-----------|------|-------------|
| `lane_id` | `str` | Lane identifier |

**Returns:** `"FORWARD"` | `"BACKWARD"` | `"BIDIRECTION"` | `"UNKNOWN"`

---

### `map.is_driving_lane(lane_id)`

| Parameter | Type | Description |
|-----------|------|-------------|
| `lane_id` | `str` | Lane identifier |

**Returns:** `bool` -- `true` if lane type is `CITY_DRIVING`

---

### `map.get_lane_type(lane_id)`

| Parameter | Type | Description |
|-----------|------|-------------|
| `lane_id` | `str` | Lane identifier |

**Returns:** `"CITY_DRIVING"` | `"BIKING"` | `"SIDEWALK"` | `"PARKING"` | `"SHOULDER"`

---

### `map.get_lane_boundary_types(lane_id)`

| Parameter | Type | Description |
|-----------|------|-------------|
| `lane_id` | `str` | Lane identifier |

**Returns:** `{"left": "<type>", "right": "<type>"}`

Boundary types: `UNKNOWN`, `DOTTED_YELLOW`, `DOTTED_WHITE`, `SOLID_YELLOW`, `SOLID_WHITE`, `DOUBLE_YELLOW`, `CURB`

---

### `map.get_lane_traffic_lights(lane_id)`

Get traffic light signal IDs that affect a given lane.

| Parameter | Type | Description |
|-----------|------|-------------|
| `lane_id` | `str` | Lane identifier |

**Returns:** `list[str]` -- Signal IDs

---

### `map.get_traffic_light_stop_line(signal_id)`

Get the stop line geometry for a traffic light.

| Parameter | Type | Description |
|-----------|------|-------------|
| `signal_id` | `str` | Traffic light signal ID |

**Returns:** `list[[x, y]]` -- Stop line coordinates

---

## Lane APIs (`map.lane.*`)

### `map.lane.get_all(contain_junction, lane_type)`

Get all lane IDs matching the criteria.

| Parameter | Type | Description |
|-----------|------|-------------|
| `contain_junction` | `bool` | Include junction lanes |
| `lane_type` | `str` | Filter by type (e.g., `"CITY_DRIVING"`) |

**Returns:** `list[str]` -- Lane IDs

---

### `map.lane.get_central_curve(lane_id)`

**Returns:** `list[[x, y]]` -- Center line points

### `map.lane.get_left_boundary_curve(lane_id)`

**Returns:** `list[[x, y]]` -- Left boundary points

### `map.lane.get_right_boundary_curve(lane_id)`

**Returns:** `list[[x, y]]` -- Right boundary points

---

### `map.lane.get_length(lane_id)`

**Returns:** `float` -- Lane length in meters

### `map.lane.get_speed_limit(lane_id)`

**Returns:** `float` -- Speed limit in m/s

---

### `map.lane.get_polygon(lane_id)`

**Returns:** `list[[x, y]]` -- Lane polygon boundary

---

### `map.lane.get_coordinate(lane_id, s, l)`

Convert Frenet coordinates to world coordinates.

| Parameter | Type | Description |
|-----------|------|-------------|
| `lane_id` | `str` | Lane identifier |
| `s` | `float` | Longitudinal position |
| `l` | `float` | Lateral offset |

**Returns:** `(x, y, heading)`

---

### `map.lane.find_lane_id(x, y)`

Find lane at world position.

**Returns:** `{"lane_id": str, "s": float}`

---

### Lane Topology

```python
map.lane.get_successor_ids(lane_id)                    # -> list[str]
map.lane.get_predecessor_ids(lane_id)                  # -> list[str]
map.lane.get_left_neighbor_forward_lane_ids(lane_id)   # -> list[str]
map.lane.get_right_neighbor_forward_lane_ids(lane_id)  # -> list[str]
map.lane.get_left_neighbor_reverse_lane_ids(lane_id)   # -> list[str]
map.lane.get_right_neighbor_reverse_lane_ids(lane_id)  # -> list[str]
```

---

### `map.lane.find_path(start_lane_id, end_lane_id)`

Find shortest path between two lanes using Dijkstra's algorithm on the lane connectivity graph.

| Parameter | Type | Description |
|-----------|------|-------------|
| `start_lane_id` | `str` | Starting lane |
| `end_lane_id` | `str` | Target lane |

**Returns:** `list[str]` -- Ordered list of lane IDs forming the path
