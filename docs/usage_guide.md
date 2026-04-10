# TrafficSandbox Usage Guide

## Prerequisites

- Docker installed and running
- Python 3.8+ (for client scripts)
- Required Python packages: `pyzmq`, `tinyrpc==1.1.7`, `msgpack`, `loguru`

```bash
pip install pyzmq tinyrpc==1.1.7 msgpack loguru
```

## 1. Starting the Sandbox

### Option A: Docker (Recommended)

```bash
# Build the image
cd TrafficSandbox
docker build -t trafficsandbox:latest .

# Run the container
docker run --name sandbox --rm -d \
    -p 10667:10667 \
    -p 8888:8888 \
    trafficsandbox:latest \
    bash -c "python /app/app.py --fps 100"
```

### Option B: Local Python

```bash
cd TrafficSandbox
pip install -r requirements.txt
python app.py --fps 100
```

### CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--fps` | `100` | Target simulation frames per second |
| `--rpc-port` | `10667` | RPC server port |
| `--vis-port` | `18888` | Visualization frontend port |

For example, if the default ports are occupied:

```bash
python app.py --fps 100 --rpc-port 10668 --vis-port 19888
```

## 2. RPC Client Setup

TrafficSandbox uses MessagePack-RPC over ZMQ. The `DotRPCProxy` helper class enables dot-notation for hierarchical API calls (e.g., `proxy.sim.reset()`).

```python
import zmq
from tinyrpc import RPCClient
from tinyrpc.protocols.msgpackrpc import MSGPACKRPCProtocol
from tinyrpc.transports.zmq import ZmqClientTransport

class DotRPCProxy:
    """Proxy that supports dot-notation for nested RPC namespaces."""
    def __init__(self, client, prefix="", one_way=False):
        self.client = client
        self.prefix = prefix
        self.one_way = one_way

    def __getattr__(self, name):
        new_prefix = f"{self.prefix}.{name}" if self.prefix else name
        return DotRPCProxy(self.client, new_prefix, self.one_way)

    def __call__(self, *args, **kwargs):
        return self.client.call(self.prefix, list(args), {}, one_way=self.one_way)

# Connect
ctx = zmq.Context()
transport = ZmqClientTransport.create(ctx, "tcp://127.0.0.1:10667")
client = RPCClient(MSGPACKRPCProtocol(), transport)
proxy = DotRPCProxy(client)
```

## 3. Loading a Map

Before creating actors, you must load an HD map:

```python
proxy.load_map("san_mateo")

# Verify
current_map = proxy.map.get_current_map()
print(f"Loaded map: {current_map}")
```

Available maps: `borregas_ave`, `san_mateo`, `SanFrancisco`, `sunnyvale`, `sunnyvale_loop`

## 4. Creating Actors

### Vehicles

```python
# Standard vehicle (kinematic steering model)
proxy.sim.create_actor({
    "actor_id": "npc_1",
    "actor_type": "vehicle.lincoln.mkz",
    "x": 587078.0,
    "y": 4141416.0,
    "z": 0.0,
    "heading": 1.57  # radians
})

# Perfect-control vehicle (directly sets heading)
proxy.sim.create_actor({
    "actor_id": "ego_1",
    "actor_type": "vehicle.lincoln.mkz.perfect",
    "x": 587080.0,
    "y": 4141420.0,
    "z": 0.0,
    "heading": 1.57
})
```

### Pedestrians

```python
proxy.sim.create_actor({
    "actor_id": "walker_1",
    "actor_type": "walker.pedestrian.normal",
    "x": 587075.0,
    "y": 4141410.0,
    "z": 0.0,
    "heading": 0.0
})
```

### Static Objects

```python
proxy.sim.create_actor({
    "actor_id": "cone_1",
    "actor_type": "static.traffic_cone",
    "x": 587070.0,
    "y": 4141415.0,
    "z": 0.0,
    "heading": 0.0
})
```

### Traffic Lights (Signals)

Traffic lights are created separately from actors:

```python
proxy.sim.create_signal({
    "signal_id": "tl_1",
    "signal_type": "signal.traffic_light",
    "signal_state": "green"
})
```

## 5. Running the Simulation

```python
# Set all actors to ready
proxy.sim.set_actor_status("npc_1", "ready")
proxy.sim.set_actor_status("ego_1", "ready")

# Start the simulation loop
proxy.sim.start_scenario()

# Check status
status = proxy.sim.get_scenario_status()  # "running" or "waiting"
```

## 6. Controlling Actors

### Vehicle Control (Standard)

```python
# throttle [0,1], steer [-1,1], brake [0,1], reverse bool
proxy.sim.apply_vehicle_control("npc_1", {
    "throttle": 0.5,
    "steer": 0.0,
    "brake": 0.0,
    "reverse": False
})
```

### Vehicle Control (Perfect)

```python
# acceleration (m/s^2), heading (radians)
proxy.sim.apply_vehicle_control("ego_1", {
    "acceleration": 2.0,
    "heading": 1.57,
    "throttle": 0.0,
    "brake": 0.0,
    "steer": 0.0,
    "reverse": False
})
```

### Walker Control

```python
# acceleration [-10, 10] m/s^2, heading (radians)
proxy.sim.apply_walker_action("walker_1", {
    "acceleration": 1.5,
    "heading": 0.0
})
```

### Traffic Light Control

```python
proxy.sim.set_signal_state("tl_1", "red")    # "green", "red", "yellow"
```

### Static Object Teleportation

```python
proxy.sim.set_static_location("cone_1", {
    "x": 587072.0, "y": 4141418.0, "z": 0.0,
    "pitch": 0.0, "yaw": 0.0, "roll": 0.0
})
```

## 7. Reading State

### Full World Snapshot

```python
snapshot = proxy.sim.get_snapshot()
# Returns: {time, scenario_running, actors, signals}

for actor_id, actor_data in snapshot["actors"].items():
    print(f"{actor_id}: speed={actor_data['speed']:.2f} m/s")
```

### Single Actor

```python
actor = proxy.sim.get_actor("npc_1")
print(f"Position: ({actor['location']['x']}, {actor['location']['y']})")
print(f"Speed: {actor['speed']} m/s")
```

### Timing Information

```python
time_info = proxy.sim.get_time()
# {frame, game_time, real_time_elapsed, real_fps, target_fps, server_time}
```

## 8. Map Queries

### Find Lane at Position

```python
result = proxy.map.find_lane_id(587078.0, 4141416.0)
lane_id = result["lane_id"]
s = result["s"]  # longitudinal position along lane
```

### Get Waypoint

```python
wp = proxy.map.get_waypoint(lane_id, s=10.0, l=0.0)
# {lane_id, is_junction, s, l, x, y, heading, speed_limit}
```

### Lane Navigation

```python
# Get next waypoints (ahead by distance)
next_wps = proxy.map.get_next_waypoint(lane_id, s, l=0.0, distance=20.0)

# Get previous waypoints
prev_wps = proxy.map.get_previous_waypoint(lane_id, s, l=0.0, distance=10.0)
```

### Lane Properties

```python
speed_limit = proxy.map.get_speed_limit(lane_id)         # m/s
heading = proxy.map.get_lane_heading(lane_id, s=10.0)     # radians
direction = proxy.map.get_lane_direction(lane_id)          # FORWARD/BACKWARD/BIDIRECTION
is_driving = proxy.map.is_driving_lane(lane_id)            # bool
lane_type = proxy.map.get_lane_type(lane_id)               # CITY_DRIVING/BIKING/SIDEWALK/...
boundaries = proxy.map.get_lane_boundary_types(lane_id)    # {left, right}
```

### Lane Topology (via `map.lane.*`)

```python
# Get all driving lanes
lanes = proxy.map.lane.get_all(False, "CITY_DRIVING")  # (contain_junction, lane_type)

# Lane geometry
curve = proxy.map.lane.get_central_curve(lane_id)       # [[x,y], ...]
length = proxy.map.lane.get_length(lane_id)              # float (meters)

# Lane connectivity
successors = proxy.map.lane.get_successor_ids(lane_id)
predecessors = proxy.map.lane.get_predecessor_ids(lane_id)
left_neighbors = proxy.map.lane.get_left_neighbor_forward_lane_ids(lane_id)
right_neighbors = proxy.map.lane.get_right_neighbor_forward_lane_ids(lane_id)

# Pathfinding
path = proxy.map.lane.find_path(start_lane_id, end_lane_id)  # list of lane IDs
```

### Traffic Light Queries

```python
# Get traffic lights affecting a lane
tl_ids = proxy.map.get_lane_traffic_lights(lane_id)

# Get stop line geometry for a traffic light
stop_line = proxy.map.get_traffic_light_stop_line(tl_id)  # [[x,y], ...]
```

## 9. Cleanup

```python
# Stop simulation
proxy.sim.stop_scenario()

# Remove specific actors
proxy.sim.remove_actor("npc_1")
proxy.sim.remove_signal("tl_1")

# Or reset everything
proxy.sim.reset()

# Shutdown the server (if needed)
proxy.shutdown()
```

## 10. Visualization

Open `http://localhost:18888` in a browser to see the real-time visualization.

**Controls:**
| Action | Input |
|--------|-------|
| Pan | Left-click + drag |
| Zoom | Mouse wheel |
| Rotate | Right-click + drag |
| Reset view | Click "Reset View" button |

**Color coding:**
| Color | Meaning |
|-------|---------|
| Blue | Vehicles |
| Red | ADS (autonomous) vehicles |
| Orange | Walkers/Pedestrians |
| Teal | Bicycles |
| Purple | Static objects |

## Complete Example

```python
import zmq
import time
from tinyrpc import RPCClient
from tinyrpc.protocols.msgpackrpc import MSGPACKRPCProtocol
from tinyrpc.transports.zmq import ZmqClientTransport

class DotRPCProxy:
    def __init__(self, client, prefix="", one_way=False):
        self.client = client
        self.prefix = prefix
        self.one_way = one_way

    def __getattr__(self, name):
        new_prefix = f"{self.prefix}.{name}" if self.prefix else name
        return DotRPCProxy(self.client, new_prefix, self.one_way)

    def __call__(self, *args, **kwargs):
        return self.client.call(self.prefix, list(args), {}, one_way=self.one_way)

# Connect
ctx = zmq.Context()
transport = ZmqClientTransport.create(ctx, "tcp://127.0.0.1:10667")
client = RPCClient(MSGPACKRPCProtocol(), transport)
proxy = DotRPCProxy(client)

# Setup
proxy.load_map("borregas_ave")
proxy.sim.reset()

# Get a random lane to place the vehicle on
lanes = proxy.map.lane.get_all(False, "CITY_DRIVING")
lane_id = lanes[0]
curve = proxy.map.lane.get_central_curve(lane_id)
start_x, start_y = curve[0]
heading = proxy.map.get_lane_heading(lane_id, 0.0)

# Create vehicle at lane start
proxy.sim.create_actor({
    "actor_id": "test_car",
    "actor_type": "vehicle.lincoln.mkz",
    "x": start_x, "y": start_y, "z": 0.0,
    "heading": heading
})
proxy.sim.set_actor_status("test_car", "ready")

# Run simulation
proxy.sim.start_scenario()

for i in range(500):
    proxy.sim.apply_vehicle_control("test_car", {
        "throttle": 0.3,
        "steer": 0.0,
        "brake": 0.0,
        "reverse": False
    })
    time.sleep(0.01)

    if i % 100 == 0:
        actor = proxy.sim.get_actor("test_car")
        print(f"Frame {i}: speed={actor['speed']:.2f} m/s")

# Cleanup
proxy.sim.stop_scenario()
proxy.sim.reset()
```
