import os
import sys
import zmq
import time
import types
import threading

from datetime import datetime
from loguru import logger
from tinyrpc.server import RPCServer
from tinyrpc.transports.zmq import ZmqServerTransport
from tinyrpc.protocols.msgpackrpc import MSGPACKRPCProtocol as MsgpackRPCProtocol
from tinyrpc.dispatch import RPCDispatcher
from zmq.error import ContextTerminated, ZMQError

from flask import Flask, render_template
from flask_socketio import SocketIO

from config import Config
from common.utils import discover_modules
from common.rpc_utils import register_module_api, sandbox_api, _RPC_CONTEXT

from simulator import Simulator
from map_toolkit import MapManager


class GracefulRPCServer(RPCServer):
    """RPCServer subclass that can be stopped cleanly."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._running = True

    def serve_forever(self):
        logger.info("[RPC] Server loop started.")
        while self._running:
            try:
                self.receive_one_message()
            except ContextTerminated:
                logger.info("[RPC] ZMQ context terminated.")
                break
            except ZMQError as e:
                if e.errno in (156384763, 88):
                    logger.info("[RPC] ZMQ socket closed.")
                else:
                    logger.warning(f"[RPC] ZMQ error: {e}")
                break
            except Exception as e:
                logger.error(f"[RPC] Loop error: {e}")
                break
        logger.info("[RPC] serve_forever() exited.")

    def stop(self):
        self._running = False
        try:
            if hasattr(self.transport, "socket"):
                self.transport.socket.close(linger=0)
            if hasattr(self.transport, "context"):
                self.transport.context.term()
        except Exception as e:
            logger.warning(f"[RPC] Socket close error: {e}")


class TrafficSandbox:
    """Main sandbox server: simulation + map + RPC + visualization."""

    def __init__(self, fps: float = 100.0):
        self.host = "0.0.0.0"
        self.timeout = 120.0
        self.shutdown_requested = False

        # Core components
        self.sim = Simulator(fps=fps)
        self.map = MapManager()

        # RPC server (ZMQ + msgpack)
        self._ctx = zmq.Context()
        self.dispatcher = RPCDispatcher()
        self.dispatcher.root_object = self
        register_module_api(self.dispatcher, self)
        self._patch_dispatcher_debug()

        self.transport = ZmqServerTransport.create(
            self._ctx, f"tcp://{self.host}:{Config.RPC_PORT}"
        )
        self.server = GracefulRPCServer(
            transport=self.transport,
            protocol=MsgpackRPCProtocol(),
            dispatcher=self.dispatcher,
        )

        # Visualization server (Flask + SocketIO)
        self.app = Flask(__name__)
        self.app.config["SECRET_KEY"] = "secret!"
        self.socketio = SocketIO(
            self.app,
            async_mode="threading",
            cors_allowed_origins="*",
            logger=False,
            engineio_logger=False,
        )
        self._setup_routes()
        threading.Thread(target=self._traffic_dataflow, daemon=True).start()

    # ------------------------------------------------------------------
    # RPC endpoints
    # ------------------------------------------------------------------

    @sandbox_api("set_timeout")
    def set_timeout(self, timeout: float):
        self.timeout = timeout
        return {"timeout": self.timeout}

    @sandbox_api(name="load_map")
    def load_map(self, map_name: str):
        logger.info(f"[Sandbox] Loading map: {map_name}")
        self._emit_safe("map_loading_start", {"map_name": map_name})

        try:
            self.map.load_map(map_name)
            new_map_data = self.map.get_render_data()
        except Exception as e:
            logger.error(f"[Sandbox] Failed to load map {map_name}: {e}")
            self._emit_safe("map_loading_error", {"error": str(e)})
            return {"status": "error", "message": str(e)}

        self._emit_safe("init_map", new_map_data)
        self._emit_safe("map_loading_done", {"map_name": map_name})
        logger.info(f"[Sandbox] Map {map_name} loaded and sent to frontend.")
        return {"status": "ok", "map": map_name}

    @sandbox_api(name="shutdown")
    def shutdown(self):
        logger.info("[Sandbox] Shutdown requested.")
        response = {"status": "ok", "message": "Server shutting down."}
        self.shutdown_requested = True
        threading.Thread(target=self._async_cleanup, daemon=True).start()
        return response

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        logger.info("Starting TrafficSandbox...")
        self.sim.start(blocking=False)
        threading.Thread(target=self._start_flask, daemon=True).start()

        logger.info(f"RPC server listening on tcp://{self.host}:{Config.RPC_PORT}")
        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            self.shutdown()
        finally:
            logger.info("[Main] Cleanup done.")
            time.sleep(0.5)
            sys.exit(0)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    # High-frequency RPC methods that should only log at DEBUG level
    _QUIET_METHODS = frozenset({
        "sim.get_snapshot", "sim.get_time", "sim.get_actor", "sim.get_signal",
        "sim.apply_vehicle_control", "sim.apply_walker_action",
        "sim.get_scenario_status",
    })

    def _patch_dispatcher_debug(self):
        """Wrap the dispatcher to log RPC calls and set RPC context."""
        orig_dispatch = self.dispatcher.dispatch

        def debug_dispatch(self_disp, request, caller=None):
            try:
                _RPC_CONTEXT.active = True
                method = request.method
                if method in TrafficSandbox._QUIET_METHODS:
                    logger.debug(f"[RPC] {method}")
                else:
                    logger.info(f"[RPC] {method} args={getattr(request, 'args', None)}")
                return orig_dispatch(request, caller)
            except Exception as e:
                logger.exception(f"[RPC] Exception in {request.method}: {e}")
                raise
            finally:
                _RPC_CONTEXT.active = False

        self.dispatcher.dispatch = types.MethodType(debug_dispatch, self.dispatcher)

    def _emit_safe(self, event: str, data):
        try:
            self.socketio.emit(event, data)
        except Exception as e:
            logger.warning(f"[SocketIO] Failed to emit '{event}': {e}")

    def _traffic_dataflow(self):
        """Background thread: push world state to the visualization frontend."""
        logger.info("[Sandbox] Visualization dataflow started.")
        while not self.shutdown_requested:
            try:
                snapshot = self.sim.get_snapshot()
                time_info = snapshot.get("time", {})

                # Convert actors dict -> list for frontend
                actors_dict = snapshot.get("actors", {})
                actors_list = list(actors_dict.values()) if isinstance(actors_dict, dict) else actors_dict

                # Send only active signal states (stop_line geometry is in map data)
                signals_dict = snapshot.get("signals", {})
                traffic_lights_list = []
                if isinstance(signals_dict, dict):
                    for sig in signals_dict.values():
                        traffic_lights_list.append({
                            "id": sig.get("id", ""),
                            "state": sig.get("state", "unknown"),
                        })

                traffic_data = {
                    "map_name": self.map.get_current_map(),
                    "frame": time_info.get("frame", 0),
                    "game_time": time_info.get("game_time", 0.0),
                    "real_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "actors": actors_list,
                    "traffic_lights": traffic_lights_list,
                }
                self.socketio.start_background_task(self._emit_traffic, traffic_data)
                time.sleep(0.05)
            except Exception as e:
                logger.warning(f"[Sandbox] Dataflow error: {e}")
                time.sleep(1.0)

    def _emit_traffic(self, data):
        self._emit_safe("traffic_update", data)

    def _setup_routes(self):
        @self.app.route("/")
        def index():
            return render_template("index.html")

    def _start_flask(self):
        logger.info(f"[Vis] Flask server on {self.host}:{Config.VIS_PORT}")
        try:
            self.socketio.run(
                self.app,
                host=self.host,
                port=Config.VIS_PORT,
                debug=False,
                use_reloader=False,
                log_output=False,
            )
        except Exception as e:
            logger.error(f"[Vis] Server error: {e}")

    def _async_cleanup(self):
        time.sleep(0.2)

        try:
            self.sim.shutdown()
        except Exception as e:
            logger.warning(f"[Shutdown] Simulator: {e}")

        try:
            if hasattr(self.transport, "socket"):
                self.transport.socket.close(linger=0)
            if hasattr(self, "_ctx"):
                self._ctx.term()
        except Exception as e:
            logger.warning(f"[Shutdown] ZMQ transport: {e}")

        try:
            if hasattr(self.server, "stop"):
                self.server.stop()
        except Exception as e:
            logger.warning(f"[Shutdown] RPC server: {e}")

        logger.info("[Shutdown] All components stopped.")


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    discover_modules(os.path.dirname(os.path.abspath(__file__)))

    import argparse
    parser = argparse.ArgumentParser(description="TrafficSandbox RPC server")
    parser.add_argument("--fps", type=float, default=100.0)
    parser.add_argument("--rpc-port", type=int, default=10667)
    parser.add_argument("--vis-port", type=int, default=18888)
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Log level (default: INFO, use DEBUG to see high-frequency RPC calls)")
    args = parser.parse_args()

    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)

    Config.log_dir = log_dir
    Config.debug = args.log_level == "DEBUG"
    Config.fps = args.fps
    Config.RPC_PORT = args.rpc_port
    Config.VIS_PORT = args.vis_port

    level = args.log_level
    logger.configure(handlers=[{"sink": sys.stderr, "level": level}])
    logger.add(
        os.path.join(log_dir, "run.log"),
        level=level,
        mode="a",
        rotation="5 MB",
        retention=3,
        compression="gz",
    )

    sandbox = TrafficSandbox(fps=Config.fps)
    sandbox.start()
