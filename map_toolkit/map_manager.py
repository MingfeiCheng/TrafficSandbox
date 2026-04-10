import copy
import json
import os.path
import pickle

import networkx as nx

from loguru import logger
from typing import List, Dict, Optional
from collections import defaultdict
from shapely.geometry import LineString

from .junction import JunctionManager
from .crosswalk import CrosswalkManager
from .road_lane import RoadLaneManager
from .stop_sign import StopSignManager
from .traffic_light import TrafficLightManager
from .waypoint import Waypoint

from common.rpc_utils import sandbox_api


class MapManager:

    def __init__(self):
        self.map_name = None
        self.render_data = None
        self.junction = JunctionManager()
        self.crosswalk = CrosswalkManager()
        self.lane = RoadLaneManager()
        self.stop_sign = StopSignManager()
        self.traffic_light = TrafficLightManager()

    def reset(self):
        self.map_name = None
        self.render_data = None
        self.junction = JunctionManager()
        self.crosswalk = CrosswalkManager()
        self.lane = RoadLaneManager()
        self.stop_sign = StopSignManager()
        self.traffic_light = TrafficLightManager()

    def load_map(self, map_name: str):
        self.reset()

        if map_name == self.map_name and self.map_name is not None:
            logger.info(f"Map {map_name} already loaded, skip.")
            return

        self.map_name = map_name
        map_root_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        back_file = os.path.join(map_root_dir, map_name, "map.pickle")
        with open(back_file, "rb") as f:
            backend_dict = pickle.load(f)

        for k, v in backend_dict.items():
            getattr(self, k).load(v)

        self.render_data = self.get_render_data()
        logger.info(f"Map loaded from {back_file}")

    # ------------------------------------------------------------------
    # Basic queries
    # ------------------------------------------------------------------

    @sandbox_api("get_current_map")
    def get_current_map(self) -> str:
        return self.map_name

    @sandbox_api("get_render_data")
    def get_render_data(self) -> Dict:
        render_data = {
            "map_name": self.map_name,
            "lanes": [],
            "stop_signs": [],
        }

        for lane_id in self.lane.get_all():
            render_data["lanes"].append({
                "id": lane_id,
                "type": self.lane.get_type(lane_id),
                "central": self.lane.get_central_curve(lane_id),
                "left_boundary": self.lane.get_left_boundary_curve(lane_id),
                "right_boundary": self.lane.get_right_boundary_curve(lane_id),
                "left_boundary_type": self.lane.get_left_boundary_type(lane_id),
                "right_boundary_type": self.lane.get_right_boundary_type(lane_id),
                "polygon": self.lane.get_polygon(lane_id),
            })

        for ss_id in self.stop_sign.get_all():
            render_data["stop_signs"].append({
                "id": ss_id,
                "stop_line": self.stop_sign.get_line(ss_id),
            })

        return render_data

    # ------------------------------------------------------------------
    # Waypoint queries
    # ------------------------------------------------------------------

    @sandbox_api("get_waypoint")
    def get_waypoint(self, lane_id: str, s: float, l: float) -> Dict:
        """Get a waypoint at (lane_id, s, l)."""
        x, y, heading = self.lane.get_coordinate(lane_id, s, l)
        return Waypoint(
            lane_id=lane_id,
            is_junction=self.lane.is_junction_lane(lane_id),
            s=s, l=l, x=x, y=y,
            heading=heading,
            speed_limit=self.lane.get_speed_limit(lane_id),
        ).to_dict()

    @sandbox_api("get_next_waypoint")
    def get_next_waypoint(self, lane_id: str, s: float, l: float, distance: float) -> List[Dict]:
        """Get next waypoint(s) at *distance* ahead, following lane connectivity."""
        return self._advance_waypoint(lane_id, s, l, distance, forward=True)

    @sandbox_api("get_previous_waypoint")
    def get_previous_waypoint(self, lane_id: str, s: float, l: float, distance: float) -> List[Dict]:
        """Get previous waypoint(s) at *distance* behind, following lane connectivity."""
        return self._advance_waypoint(lane_id, s, l, distance, forward=False)

    def _get_direction_str(self, lane_id: str) -> str:
        """Get lane direction as a normalized string."""
        raw = self.lane.get_direction(lane_id)
        if isinstance(raw, int):
            return self._DIRECTION_MAP.get(raw, "UNKNOWN")
        return raw

    def _advance_waypoint(self, lane_id: str, s: float, l: float,
                          distance: float, forward: bool) -> List[Dict]:
        """Shared logic for get_next_waypoint / get_previous_waypoint."""
        lane_length = self.lane.get_length(lane_id)
        direction = self._get_direction_str(lane_id)

        # Direction-aware longitudinal update
        if direction == "BACKWARD":
            sign = -1.0 if forward else 1.0
        else:  # FORWARD, BIDIRECTION, UNKNOWN
            sign = 1.0 if forward else -1.0
        next_s = s + sign * distance

        # Case 1: still within lane boundary
        if 0.0 <= next_s <= lane_length:
            return [self._make_waypoint(lane_id, next_s, l)]

        # Case 2: beyond lane boundary → follow connectivity
        if forward:
            if direction == "BACKWARD":
                next_lanes = self.lane.get_predecessor_ids(lane_id)
                remaining = abs(next_s)
            else:
                next_lanes = self.lane.get_successor_ids(lane_id)
                remaining = next_s - lane_length
        else:
            if direction == "BACKWARD":
                next_lanes = self.lane.get_successor_ids(lane_id)
                remaining = abs(next_s - lane_length)
            else:
                next_lanes = self.lane.get_predecessor_ids(lane_id)
                remaining = abs(next_s)

        if not next_lanes:
            return []

        waypoints = []
        for nxt in next_lanes:
            nxt_len = self.lane.get_length(nxt)
            if forward:
                nxt_s = min(max(remaining, 0.0), nxt_len - 0.01)
            else:
                nxt_s = max(nxt_len - remaining, 0.01)
            waypoints.append(self._make_waypoint(nxt, nxt_s, l))
        return waypoints

    def _make_waypoint(self, lane_id: str, s: float, l: float) -> Dict:
        x, y, heading = self.lane.get_coordinate(lane_id, s, l)
        return Waypoint(
            lane_id=lane_id,
            is_junction=self.lane.is_junction_lane(lane_id),
            s=s, l=l, x=x, y=y,
            heading=heading,
            speed_limit=self.lane.get_speed_limit(lane_id),
        ).to_dict()

    # ------------------------------------------------------------------
    # Lane-level convenience APIs (delegating to self.lane)
    #
    # These provide a flat RPC namespace (map.find_lane_id, map.get_speed_limit,
    # etc.) so clients don't need to traverse nested sub-objects.
    # ------------------------------------------------------------------

    @sandbox_api("find_lane_id")
    def find_lane_id(self, x: float, y: float) -> Dict:
        """Find the lane containing position (x, y).

        Returns: {"lane_id": str | None, "s": float}
        """
        return self.lane.find_lane_id(x, y)

    @sandbox_api("get_speed_limit")
    def get_speed_limit(self, lane_id: str) -> float:
        """Get the speed limit (m/s) for a lane."""
        return self.lane.get_speed_limit(lane_id)

    @sandbox_api("get_lane_heading")
    def get_lane_heading(self, lane_id: str, s: float) -> float:
        """Get the lane heading (radians) at longitudinal position *s*."""
        _, _, heading = self.lane.get_coordinate(lane_id, s, 0.0)
        return heading

    _DIRECTION_MAP = {1: "FORWARD", 2: "BACKWARD", 3: "BIDIRECTION"}

    @sandbox_api("get_lane_direction")
    def get_lane_direction(self, lane_id: str) -> str:
        """Get the lane direction: FORWARD, BACKWARD, BIDIRECTION, or UNKNOWN."""
        raw = self.lane.get_direction(lane_id)
        if isinstance(raw, int):
            return self._DIRECTION_MAP.get(raw, "UNKNOWN")
        return raw

    @sandbox_api("is_driving_lane")
    def is_driving_lane(self, lane_id: str) -> bool:
        """Check whether the lane is a CITY_DRIVING lane."""
        return self.lane.is_driving_lane(lane_id)

    @sandbox_api("get_lane_type")
    def get_lane_type(self, lane_id: str) -> str:
        """Get lane type: CITY_DRIVING, BIKING, SIDEWALK, PARKING, SHOULDER, or NONE."""
        return self.lane.get_type(lane_id)

    @sandbox_api("get_lane_boundary_types")
    def get_lane_boundary_types(self, lane_id: str) -> Dict:
        """Get the left and right boundary types for a lane.

        Returns: {"left": str, "right": str}
        e.g. {"left": "SOLID_YELLOW", "right": "DOTTED_WHITE"}
        """
        return {
            "left": self.lane.get_left_boundary_type(lane_id),
            "right": self.lane.get_right_boundary_type(lane_id),
        }

    @sandbox_api("get_lane_traffic_lights")
    def get_lane_traffic_lights(self, lane_id: str) -> List[str]:
        """Get the traffic light signal IDs that govern the given lane.

        Returns an empty list if no traffic lights are associated.
        """
        if self.lane.lanes_traffic_light is None:
            return []
        return list(self.lane.lanes_traffic_light.get(lane_id, []))

    @sandbox_api("get_traffic_light_stop_line")
    def get_traffic_light_stop_line(self, signal_id: str) -> List[List[float]]:
        """Get the stop line coordinates [[x,y], ...] for a traffic light."""
        return self.traffic_light.get_stop_line(signal_id)
