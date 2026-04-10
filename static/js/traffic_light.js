import { applyMapTransform } from "./map.js";

const canvas = document.getElementById("trafficLightCanvas");
const ctx = canvas.getContext("2d");

// Map-based traffic light stop lines (loaded once with map data)
let mapTrafficLights = null;
// Active signal states from sim (updated via traffic_update)
let activeSignals = null;

const TL_COLORS = {
  "green":    "#22c55e",
  "red":      "#ef4444",
  "yellow":   "#eab308",
  "inactive": "#555566",
  "unknown":  "#6b7280",
};

// Called when map data is loaded (init_map)
export function setMapTrafficLights(tls) {
  mapTrafficLights = tls;
}

// Called on each traffic_update
export function setTrafficLightData(tls) {
  activeSignals = {};
  if (tls) {
    for (const tl of tls) {
      activeSignals[tl.id] = tl.state || "unknown";
    }
  }
}

export function updateTrafficLights(tls) {
  setTrafficLightData(tls);
  drawTrafficLight();
}

export function drawTrafficLight() {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
    canvas.width = w * dpr;
    canvas.height = h * dpr;
  }

  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  if (!mapTrafficLights || mapTrafficLights.length === 0) return;

  ctx.save();
  applyMapTransform(ctx, w, h);
  ctx.lineCap = "round";

  for (const tl of mapTrafficLights) {
    const stopLine = tl.stop_line;
    if (!stopLine || stopLine.length < 2) continue;

    // Use active signal state if available, otherwise "inactive"
    const state = (activeSignals && activeSignals[tl.id]) || "inactive";
    const color = TL_COLORS[state] || TL_COLORS.inactive;

    ctx.strokeStyle = color;
    ctx.lineWidth = 0.35;
    ctx.beginPath();
    ctx.moveTo(stopLine[0][0], stopLine[0][1]);
    for (let i = 1; i < stopLine.length; i++) {
      ctx.lineTo(stopLine[i][0], stopLine[i][1]);
    }
    ctx.stroke();
  }

  ctx.restore();
}
