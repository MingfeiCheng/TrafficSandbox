import { mapBounds } from "./map.js";

export const minScale = 0.5;
export const maxScale = 100;
export const rotationStep = 0.003;

let offsetX = 0;
let offsetY = 0;
let scale = 1;
let rotationAngle = 0;

export function getTransform() {
  return { offsetX, offsetY, scale, rotationAngle };
}

export function getMapCenter() {
  if (!mapBounds || !mapBounds.max_x) return { cx: 0, cy: 0 };
  return {
    cx: (mapBounds.max_x + mapBounds.min_x) / 2,
    cy: (mapBounds.max_y + mapBounds.min_y) / 2,
  };
}

export function setTransform({ x, y, s, r }) {
  if (s !== undefined) scale = Math.min(Math.max(s, minScale), maxScale);
  if (r !== undefined) rotationAngle = r;
  if (x !== undefined) offsetX = x;
  if (y !== undefined) offsetY = y;

  // Clamp panning so the map can't be dragged entirely off-screen
  if (!mapBounds || !mapBounds.max_x) return;

  const mapWidth = mapBounds.max_x - mapBounds.min_x;
  const mapHeight = mapBounds.max_y - mapBounds.min_y;

  const container = document.querySelector(".canvas-container");
  if (!container) return;

  const vw = container.clientWidth;
  const vh = container.clientHeight;

  // Allow panning up to 1/3 of viewport beyond the map edges
  const margin = 0.33;
  const limitX = (mapWidth * scale) / 2 + vw * margin;
  const limitY = (mapHeight * scale) / 2 + vh * margin;

  offsetX = Math.min(Math.max(offsetX, -limitX), limitX);
  offsetY = Math.min(Math.max(offsetY, -limitY), limitY);
}
