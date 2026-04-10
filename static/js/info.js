let mapName = "--";
let frame = 0;
let gameTime = 0;
let realTime = 0;

export function updateInfo(newMapName, newFrame, newGameTime, newRealTime) {
    mapName = newMapName;
    frame = newFrame;
    gameTime = newGameTime;
    realTime = newRealTime;
    drawInfo();
}

export function updateActorSignalCounts(actorCount, signalCount) {
    const actorEl = document.getElementById("actorCount");
    const signalEl = document.getElementById("signalCount");
    if (actorEl) actorEl.textContent = `Actors: ${actorCount}`;
    if (signalEl) signalEl.textContent = `Signals: ${signalCount}`;
}

export function drawInfo() {
    document.getElementById("map-name").textContent = mapName;
    document.getElementById("frame").textContent = frame;
    document.getElementById("game-time").textContent = typeof gameTime === "number" ? gameTime.toFixed(2) + "s" : gameTime;
    document.getElementById("real-time").textContent = typeof realTime === "number" ? realTime.toFixed(2) + "s" : realTime;
}
