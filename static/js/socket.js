import { loadCachedMap, updateMap, drawMap, showMapLoading, updateMapLoading, hideMapLoading } from "./map.js";
import { setMapTrafficLights, setTrafficLightData, drawTrafficLight } from './traffic_light.js';
import { setActorData, drawActor } from './actor.js';
import { updateInfo, updateActorSignalCounts } from './info.js';
import { addCanvasListeners } from "./listener.js";

// --- Render loop: single rAF drives all dynamic layers ---
let needsRedraw = false;

function renderLoop() {
  if (needsRedraw) {
    drawActor();
    drawTrafficLight();
    needsRedraw = false;
  }
  requestAnimationFrame(renderLoop);
}
requestAnimationFrame(renderLoop);

export function requestRedraw() {
  needsRedraw = true;
}

// --- Cache restore ---
window.addEventListener("DOMContentLoaded", async () => {
  try {
    const lastMapName = localStorage.getItem("lastMapName") || "borregas_ave";
    const cached = await loadCachedMap(lastMapName);
    if (cached) {
      showMapLoading("Restoring cached map...");
      updateMapLoading(20);
      await updateMap(cached);
      if (cached.traffic_lights) {
        setMapTrafficLights(cached.traffic_lights);
      }
      drawMap();
      needsRedraw = true;
      updateMapLoading(100);
      setTimeout(hideMapLoading, 300);
    }
  } catch (e) {
    console.warn("[Cache]", e);
    hideMapLoading();
  }
});

// --- Socket ---
const socket = io();

const statusIndicator = document.getElementById("connectionStatus");
const connectionText = document.getElementById("connectionText");

socket.on("connect", () => {
  if (statusIndicator) statusIndicator.className = "status-indicator connected";
  if (connectionText) connectionText.textContent = "Connected";
});

socket.on("disconnect", () => {
  if (statusIndicator) statusIndicator.className = "status-indicator disconnected";
  if (connectionText) connectionText.textContent = "Disconnected";
});

socket.on("map_loading_start", (data) => {
  showMapLoading(`Loading map: ${data.map_name}`);
  updateMapLoading(5);
});

socket.on("init_map", async (mapData) => {
  updateMapLoading(60);
  await updateMap(mapData);
  // Load traffic light stop lines from map data
  if (mapData.traffic_lights) {
    setMapTrafficLights(mapData.traffic_lights);
  }
  updateMapLoading(90);
  drawMap();
  needsRedraw = true;
});

socket.on("map_loading_done", () => {
  updateMapLoading(100);
  setTimeout(hideMapLoading, 300);
});

socket.on("map_loading_error", (err) => {
  showMapLoading("Failed to load map");
  setTimeout(hideMapLoading, 1000);
});

socket.on("traffic_update", (data) => {
  updateInfo(data.map_name, data.frame, data.game_time, data.real_time);
  setActorData(data.actors);
  setTrafficLightData(data.traffic_lights);

  const actorCount = data.actors ? data.actors.length : 0;
  const signalCount = data.traffic_lights ? data.traffic_lights.length : 0;
  updateActorSignalCounts(actorCount, signalCount);

  needsRedraw = true;
});

// --- Canvas listeners ---
const mapCanvas = document.getElementById("mapCanvas");
addCanvasListeners(mapCanvas);
