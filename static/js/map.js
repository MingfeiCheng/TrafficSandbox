import { getTransform, getMapCenter } from "./view_state.js";

let mapData = null;
export const mapBounds = { min_x: 0, min_y: 0, max_x: 0, max_y: 0 };
let db = null;

const LANE_FILL = "#3d3e60";
const LANE_STROKE = "#4a4b70";

const BOUNDARY_TYPE = {
  "UNKNOWN":       { color: "#888",           style: "solid"  },
  "DOTTED_YELLOW": { color: "#eebf00",        style: "dotted" },
  "DOTTED_WHITE":  { color: "#ffffff",        style: "dotted" },
  "SOLID_YELLOW":  { color: "#eebf00",        style: "solid"  },
  "SOLID_WHITE":   { color: "#ffffff",        style: "solid"  },
  "DOUBLE_YELLOW": { color: "#eebf00",        style: "double" },
  "CURB":          { color: "#777",           style: "solid"  }
};

// ---- IndexedDB caching ----
function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open("MapCacheDB", 1);
    request.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains("maps"))
        db.createObjectStore("maps", { keyPath: "map_name" });
    };
    request.onsuccess = (e) => resolve(e.target.result);
    request.onerror = (e) => reject(e.target.error);
  });
}

async function cacheMapToDB(data) {
  if (!db) db = await openDB();
  const tx = db.transaction("maps", "readwrite");
  tx.objectStore("maps").put({ map_name: data.map_name || "unknown", timestamp: Date.now(), data });
}

export async function loadCachedMap(name) {
  if (!db) db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("maps", "readonly");
    const req = tx.objectStore("maps").get(name);
    req.onsuccess = () => resolve(req.result ? req.result.data : null);
    req.onerror = () => reject(req.error);
  });
}

export async function clearMapCache() {
  if (!db) db = await openDB();
  db.transaction("maps", "readwrite").objectStore("maps").clear();
}

// ---- Map data ----
export async function updateMap(newMapData) {
  if (!newMapData || !newMapData.lanes) return;
  mapData = newMapData;
  window.mapData = newMapData;

  let min_x = Infinity, min_y = Infinity, max_x = -Infinity, max_y = -Infinity;
  for (const lane of mapData.lanes) {
    if (!lane.polygon) continue;
    for (const [x, y] of lane.polygon) {
      if (x < min_x) min_x = x;
      if (x > max_x) max_x = x;
      if (y < min_y) min_y = y;
      if (y > max_y) max_y = y;
    }
  }
  mapBounds.min_x = min_x;
  mapBounds.min_y = min_y;
  mapBounds.max_x = max_x;
  mapBounds.max_y = max_y;

  try {
    await cacheMapToDB(newMapData);
    localStorage.setItem("lastMapName", newMapData.map_name);
  } catch (e) {
    console.warn("[MapCache]", e);
  }
  drawMap();
}

// ---- Shared transform ----
export function applyMapTransform(ctx, w, h) {
  const { offsetX, offsetY, scale, rotationAngle } = getTransform();
  const { cx, cy } = getMapCenter();
  ctx.translate(w / 2 + offsetX, h / 2 + offsetY);
  ctx.rotate(rotationAngle);
  ctx.scale(scale, scale);
  ctx.translate(-cx, -cy);
}

// ---- Rendering ----
function resizeCanvas(canvas) {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
    canvas.width = w * dpr;
    canvas.height = h * dpr;
  }
  return { w, h, dpr };
}

export function drawMap() {
  if (!mapData) return;
  const canvas = document.getElementById("mapCanvas");
  const ctx = canvas.getContext("2d");
  const { w, h, dpr } = resizeCanvas(canvas);

  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.save();
  applyMapTransform(ctx, w, h);

  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";

  // Draw lane fills
  for (const lane of mapData.lanes) {
    drawLaneFill(ctx, lane);
  }
  // Draw boundaries on top
  for (const lane of mapData.lanes) {
    drawBoundary(ctx, lane, "left_boundary", lane.left_boundary_type);
    drawBoundary(ctx, lane, "right_boundary", lane.right_boundary_type);
  }

  ctx.restore();
}

function drawLaneFill(ctx, lane) {
  const poly = lane.polygon;
  if (!poly || poly.length < 3) return;

  ctx.beginPath();
  ctx.moveTo(poly[0][0], poly[0][1]);
  for (let i = 1; i < poly.length; i++) ctx.lineTo(poly[i][0], poly[i][1]);
  ctx.closePath();

  ctx.fillStyle = LANE_FILL;
  ctx.fill();

  ctx.strokeStyle = LANE_STROKE;
  ctx.lineWidth = 0.08;
  ctx.stroke();
}

function drawBoundary(ctx, lane, key, typeKey) {
  const pts = lane[key];
  if (!pts || pts.length < 2) return;
  if (!typeKey || (!typeKey.includes("YELLOW") && !typeKey.includes("WHITE") && typeKey !== "CURB")) return;

  const style = BOUNDARY_TYPE[typeKey] || BOUNDARY_TYPE.UNKNOWN;

  ctx.save();
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.strokeStyle = style.color;
  ctx.lineWidth = style.style === "double" ? 0.4 : 0.3;

  if (style.style === "dotted") {
    ctx.setLineDash([2.5, 3]);
  } else {
    ctx.setLineDash([]);
  }

  ctx.beginPath();
  ctx.moveTo(pts[0][0], pts[0][1]);
  for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
  ctx.stroke();

  // Double line: draw a second line with slight offset
  if (style.style === "double") {
    ctx.lineWidth = 0.15;
    ctx.globalAlpha = 0.6;
    ctx.beginPath();
    ctx.moveTo(pts[0][0], pts[0][1]);
    for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
    ctx.stroke();
    ctx.globalAlpha = 1.0;
  }

  ctx.restore();
}

// ---- Loading overlay ----
export function showMapLoading(text = "Loading map...") {
  const overlay = document.getElementById("loading-bar");
  overlay.querySelector(".loading-text").textContent = text;
  overlay.style.display = "flex";
  updateMapLoading(5);
}

export function updateMapLoading(pct) {
  const bar = document.querySelector(".loading-progress-bar");
  if (bar) bar.style.width = `${Math.min(100, pct)}%`;
}

export function hideMapLoading() {
  const overlay = document.getElementById("loading-bar");
  const bar = overlay.querySelector(".loading-progress-bar");
  if (bar) bar.style.width = "100%";
  setTimeout(() => { overlay.style.display = "none"; if (bar) bar.style.width = "0%"; }, 300);
}
