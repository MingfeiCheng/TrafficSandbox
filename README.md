# TrafficSandbox

A lightweight, Docker-based traffic simulation sandbox for autonomous driving testing. It provides a physics-based simulation environment with HD map support, real-time visualization, and a MessagePack-RPC API for programmatic control.

## Features

- **Physics-based simulation** -- Bicycle/Ackermann kinematic model for vehicles, simplified dynamics for walkers
- **HD map support** -- Apollo HD map format with lane topology, traffic lights, stop signs, crosswalks, and junctions
- **Real-time visualization** -- Browser-based multi-layer canvas rendering with pan/zoom/rotate
- **RPC API** -- MessagePack-RPC over ZMQ for high-performance client-server communication
- **Extensible actor system** -- Registry-based architecture for adding custom actor types
- **Docker deployment** -- Single-container setup with configurable FPS

## Quick Start

### 1. Build & Run

```bash
cd TrafficSandbox
docker build -t trafficsandbox:latest .
docker run --name sandbox --rm -d -p 10667:10667 -p 18888:18888 \
    trafficsandbox:latest bash -c "python /app/app.py --fps 100"
```

### CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--fps` | `100` | Target simulation frames per second |
| `--rpc-port` | `10667` | RPC server port |
| `--vis-port` | `8888` | Visualization frontend port |

To use custom ports:

```bash
python app.py --fps 100 --rpc-port 10668 --vis-port 19888
```

### 2. Open Visualization

Navigate to `http://localhost:18888` in your browser.

### 3. Connect from Python

```python
from tinyrpc import RPCClient
from tinyrpc.protocols.msgpackrpc import MSGPACKRPCProtocol
from tinyrpc.transports.zmq import ZmqClientTransport
import zmq

ctx = zmq.Context()
transport = ZmqClientTransport.create(ctx, "tcp://127.0.0.1:10667")
client = RPCClient(MSGPACKRPCProtocol(), transport)
proxy = client.get_proxy()

# Load a map
proxy.load_map("san_mateo")

# Create a vehicle
proxy.call("sim.create_actor", [{
    "actor_id": "npc_1",
    "actor_type": "vehicle.lincoln.mkz",
    "x": 587078.0, "y": 4141416.0, "z": 0.0,
    "heading": 1.57
}])

# Start simulation
proxy.call("sim.start_scenario", [])

# Get world state
snapshot = proxy.call("sim.get_snapshot", [])
```

## Actor Types

| Type ID | Category | Description | Dimensions (L x W x H) |
|---------|----------|-------------|------------------------|
| `vehicle.lincoln.mkz` | Vehicle | Lincoln MKZ sedan | 4.93 x 2.11 x 1.48 m |
| `vehicle.lincoln.mkz.perfect` | Vehicle | Lincoln MKZ (perfect heading control) | 4.93 x 2.11 x 1.48 m |
| `vehicle.lincoln.mkz_lgsvl` | Vehicle | Lincoln MKZ LGSVL variant | 4.70 x 2.06 x 2.05 m |
| `vehicle.lincoln.mkz_lgsvl.perfect` | Vehicle | Lincoln MKZ LGSVL (perfect heading) | 4.70 x 2.06 x 2.05 m |
| `vehicle.bicycle.normal` | Vehicle | Bicycle | 3.00 x 1.00 x 1.80 m |
| `vehicle.bicycle.normal.perfect` | Vehicle | Bicycle (perfect heading) | 3.00 x 1.00 x 1.80 m |
| `walker.pedestrian.normal` | Walker | Pedestrian | 0.50 x 0.50 x 1.80 m |
| `static.traffic_cone` | Static | Traffic cone (immovable) | 0.35 x 0.35 x 0.70 m |
| `signal.traffic_light` | Signal | Traffic light (green/red/yellow) | N/A |

> **Normal vs Perfect**: Normal actors use kinematic steering constraints (wheelbase, steer ratio). Perfect actors directly set heading to the target value each tick -- useful for ground-truth ADS vehicles.

## Network Ports

| Port (default) | Protocol | Purpose | CLI flag |
|----------------|----------|---------|----------|
| 10667 | TCP (ZMQ msgpack-rpc) | RPC server | `--rpc-port` |
| 18888 | HTTP + WebSocket | Visualization frontend | `--vis-port` |

## Available Maps

| Map | Directory |
|-----|-----------|
| `borregas_ave` | Borregas Avenue |
| `san_mateo` | San Mateo |
| `SanFrancisco` | San Francisco |
| `sunnyvale` | Sunnyvale |
| `sunnyvale_loop` | Sunnyvale Loop |

## Directory Structure

```
TrafficSandbox/
├── app.py                  # Entry point: Flask + RPC server + SocketIO
├── simulator.py            # Simulation tick loop & actor management
├── config.py               # Global config (ports, FPS, logging)
├── Dockerfile
├── actor/
│   ├── vehicle/            # Vehicle actors (Lincoln MKZ, Bicycle)
│   ├── walker/             # Pedestrian actors
│   ├── static/             # Static objects (traffic cone)
│   ├── signal/             # Traffic signals (traffic light)
│   └── control/            # Control command dataclasses
├── common/
│   ├── rpc_utils.py        # @sandbox_api decorator & RPC registration
│   ├── data_structure.py   # Location, Waypoint, BoundingBox
│   ├── timer.py            # Frame-based simulation timer
│   └── utils.py            # Module discovery utilities
├── map_toolkit/
│   ├── map_manager.py      # MapManager (primary map query interface)
│   ├── road_lane.py        # Lane geometry, topology & pathfinding
│   ├── junction.py         # Junction management
│   ├── crosswalk.py        # Crosswalk management
│   ├── stop_sign.py        # Stop sign management
│   ├── traffic_light.py    # Traffic light management
│   └── data/               # Pre-built map pickle files
├── registry/               # Actor type registration system
├── templates/              # Flask HTML templates
├── static/                 # Frontend CSS/JS assets
├── tests/                  # Test scripts
└── docs/                   # Documentation
```

## Documentation

See the [docs/](docs/) directory for detailed documentation:

- [Usage Guide](docs/usage_guide.md) -- How to use the sandbox end-to-end
- [Architecture & Design](docs/architecture.md) -- System design and internals
- [API Reference](docs/api_reference.md) -- Complete RPC API documentation
