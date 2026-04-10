import { getTransform, setTransform, minScale, maxScale, rotationStep } from "./view_state.js";
import { drawMap } from "./map.js";
import { drawActor } from "./actor.js";
import { drawTrafficLight } from "./traffic_light.js";

let isDragging = false;
let isRotating = false;
let startX = 0, startY = 0;
let rafToken = 0;

function redrawAll() {
  cancelAnimationFrame(rafToken);
  rafToken = requestAnimationFrame(() => {
    drawMap();
    drawActor();
    drawTrafficLight();
  });
}

export function addCanvasListeners(canvas) {
  const initial = getTransform();

  canvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    const { offsetX: ox, offsetY: oy, scale } = getTransform();
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const zoomFactor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
    const newScale = Math.min(Math.max(scale * zoomFactor, minScale), maxScale);
    const ratio = newScale / scale;

    const cx = canvas.clientWidth / 2;
    const cy = canvas.clientHeight / 2;
    setTransform({
      x: mouseX - ratio * (mouseX - cx - ox) - cx,
      y: mouseY - ratio * (mouseY - cy - oy) - cy,
      s: newScale,
    });
    redrawAll();
  }, { passive: false });

  canvas.addEventListener("contextmenu", e => e.preventDefault());

  canvas.addEventListener("mousedown", (e) => {
    e.preventDefault();
    const t = getTransform();
    if (e.button === 0) {
      isDragging = true;
      startX = e.clientX - t.offsetX;
      startY = e.clientY - t.offsetY;
    } else if (e.button === 2) {
      isRotating = true;
      startX = e.clientX;
      startY = e.clientY;
    }
  });

  canvas.addEventListener("mousemove", (e) => {
    if (isDragging) {
      setTransform({ x: e.clientX - startX, y: e.clientY - startY });
      redrawAll();
    } else if (isRotating) {
      const t = getTransform();
      const dx = e.clientX - startX;
      setTransform({ r: t.rotationAngle - dx * rotationStep });
      startX = e.clientX;
      startY = e.clientY;
      redrawAll();
    }
  });

  ["mouseup", "mouseleave"].forEach(evt => {
    canvas.addEventListener(evt, () => {
      isDragging = false;
      isRotating = false;
    });
  });

  document.getElementById("resetViewButton")?.addEventListener("click", () => {
    setTransform({ x: initial.offsetX, y: initial.offsetY, s: initial.scale, r: initial.rotationAngle });
    redrawAll();
  });
}
