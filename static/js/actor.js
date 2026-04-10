import { getTransform } from "./view_state.js";
import { applyMapTransform } from "./map.js";

const actorCanvas = document.getElementById("actorCanvas");
const actorCtx = actorCanvas.getContext("2d");

let actors = null;

const ACTOR_COLORS = {
  "vehicle": "rgba(79,108,243,0.85)",
  "walker":  "rgba(245,177,8,0.85)",
  "static":  "rgba(184,29,227,0.8)",
  "bicycle": "rgba(0,175,149,0.85)",
};
const ADS_COLOR = "rgba(245,82,82,0.9)";
const DEFAULT_COLOR = "rgba(150,150,150,0.7)";

export function setActorData(newActors) {
  actors = newActors;
}

export function updateActors(newActors) {
  actors = newActors;
  drawActor();
}

export function drawActor() {
  const dpr = window.devicePixelRatio || 1;
  const w = actorCanvas.clientWidth;
  const h = actorCanvas.clientHeight;
  if (actorCanvas.width !== w * dpr || actorCanvas.height !== h * dpr) {
    actorCanvas.width = w * dpr;
    actorCanvas.height = h * dpr;
  }

  actorCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
  actorCtx.clearRect(0, 0, actorCanvas.width, actorCanvas.height);

  if (!actors || actors.length === 0) return;

  const { scale } = getTransform();

  actorCtx.save();
  applyMapTransform(actorCtx, w, h);

  for (let i = 0; i < actors.length; i++) {
    const actor = actors[i];
    const polygon = actor.polygon;
    if (!polygon || polygon.length < 3) continue;

    // Color
    const color = actor.role === "ads"
      ? ADS_COLOR
      : (ACTOR_COLORS[(actor.category || "").split(".")[0]] || DEFAULT_COLOR);

    // Fill polygon
    actorCtx.beginPath();
    actorCtx.moveTo(polygon[0][0], polygon[0][1]);
    for (let j = 1; j < polygon.length; j++) actorCtx.lineTo(polygon[j][0], polygon[j][1]);
    actorCtx.closePath();
    actorCtx.fillStyle = color;
    actorCtx.fill();

    // Heading indicator
    if (actor.location) {
      const cx = polygon.reduce((s, p) => s + p[0], 0) / polygon.length;
      const cy = polygon.reduce((s, p) => s + p[1], 0) / polygon.length;
      const yaw = actor.location.yaw || 0;
      const len = actor.bbox ? actor.bbox.length / 2 : 2;

      actorCtx.beginPath();
      actorCtx.moveTo(cx, cy);
      actorCtx.lineTo(cx + Math.cos(yaw) * len, cy + Math.sin(yaw) * len);
      actorCtx.strokeStyle = "rgba(255,255,255,0.8)";
      actorCtx.lineWidth = 0.25;
      actorCtx.stroke();
    }

    // Label
    const cx = polygon.reduce((s, p) => s + p[0], 0) / polygon.length;
    const cy = polygon.reduce((s, p) => s + p[1], 0) / polygon.length;
    const labelScale = 1 / scale;
    const id = actor.id || "";
    const speed = parseFloat(actor.speed || 0).toFixed(1);
    const label = `${id}  ${speed} m/s`;

    actorCtx.save();
    actorCtx.translate(cx, cy);
    actorCtx.scale(labelScale, labelScale);

    actorCtx.font = "11px -apple-system, sans-serif";
    const tw = actorCtx.measureText(label).width;

    actorCtx.fillStyle = "rgba(0,0,0,0.6)";
    actorCtx.beginPath();
    roundRect(actorCtx, -tw / 2 - 3, -18, tw + 6, 16, 3);
    actorCtx.fill();

    actorCtx.fillStyle = "#e8e9f3";
    actorCtx.textAlign = "center";
    actorCtx.textBaseline = "middle";
    actorCtx.fillText(label, 0, -10);
    actorCtx.restore();
  }

  actorCtx.restore();
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
}
