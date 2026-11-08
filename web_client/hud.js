/** 7BZ Dev Cloud Game streaming HUD. */
(() => {
  "use strict";
  if (window.__sevenBzHud) return;
  window.__sevenBzHud = true;

  const post = (message) => window.postMessage(message, window.location.origin);
  const value = (input, fallback = 0) => Number.isFinite(Number(input)) ? Number(input) : fallback;
  const format = (number, digits = 0) => value(number).toFixed(digits);
  const state = {
    expanded: false, qualityInitialized: false,
    rtts: [], audio: true, pointer: false, esc: false, toastTimer: 0,
    hasGamepad: false, inputMode: "mouse_keyboard",
    hidden: false, controllerMode: "desktop", keyboardOpen: false,
    padButtons: [], cursorX: .5, cursorY: .5, lastMove: 0, lastScroll: 0,
    keyIndex: 0, shifted: false, controllerBusy: false, controllerErrorAt: 0,
  };
  try { state.hidden = localStorage.getItem("sevenBzHudHidden") === "1"; } catch (_) {}

  const hud = document.createElement("section");
  hud.id = "seven-bz-hud";
  hud.setAttribute("aria-label", "7BZ streaming controls");
  hud.innerHTML = `
    <div class="seven-shell">
      <div class="seven-topbar">
        <div class="seven-brand"><i class="seven-mark"></i><span class="seven-brand-name">7BZ Dev Cloud Game</span><span class="seven-live">LIVE</span></div>
        <div class="seven-quick">
          <div class="seven-chip"><b data-stat="fps">--</b><span>Stream FPS</span></div>
          <div class="seven-chip"><b data-stat="rtt">--</b><span>Stream RTT</span></div>
          <div class="seven-chip"><b data-stat="rate">--</b><span>Video rate</span></div>
          <div class="seven-chip"><b data-stat="pad">None</b><span>Gamepad</span></div>
          <div class="seven-chip"><b data-stat="gpu">--</b><span>GPU (G0|G1)</span></div>
          <div class="seven-chip"><b data-stat="cpu">--</b><span>CPU load</span></div>
        </div>
        <button class="seven-button seven-icon-button" data-action="hide" aria-label="Hide top bar" title="Hide top bar">−</button>
        <button class="seven-button seven-icon-button" data-action="expand" aria-label="Open controls" title="Open controls">⌄</button>
      </div>
      <div class="seven-details is-collapsed">
        <div class="seven-card">
          <div class="seven-card-title"><span>Live performance</span><span data-stat="transport">WebSocket</span></div>
          <div class="seven-metrics">
            <div class="seven-metric"><strong data-stat="gpu0_metric">--</strong><small>🎮 GPU 0 Render</small></div>
            <div class="seven-metric"><strong data-stat="gpu1_metric">--</strong><small>📡 GPU 1 Stream</small></div>
            <div class="seven-metric"><strong data-stat="jitter">--</strong><small>RTT jitter</small></div>
            <div class="seven-metric"><strong data-stat="loss">--</strong><small>Frame loss</small></div>
            <div class="seven-metric"><strong data-stat="packet">N/A</strong><small>Packet loss</small></div>
          </div>
        </div>
        <div class="seven-card">
          <div class="seven-optimize">
            <div class="seven-optimize-copy"><b>Automatic stream quality</b><span data-stat="profile">720p · 60 FPS · adaptive bitrate</span></div>
            <span class="seven-live">AUTO</span>
          </div>
          <div class="seven-actions">
            <button class="seven-button" data-action="fullscreen">Fullscreen</button>
            <button class="seven-button" data-action="pointer">Gaming Mode (Lock Mouse)</button>
            <button class="seven-button" data-action="mode" data-stat="modename">🖱️ Mode: M+K</button>
            <button class="seven-button" data-action="controller">🎮 Desktop Cursor</button>
            <button class="seven-button" data-action="keyboard">⌨ On-screen Keyboard</button>
            <button class="seven-button" data-action="home">7BZ Home</button>
            <button class="seven-button" data-action="esc">Esc Lock</button>
            <button class="seven-button" data-action="audio">Audio Unmute</button>
            <button class="seven-button seven-danger" data-action="reset">Force Kill / Exit Frozen Game</button>
          </div>
        </div>
        <div class="seven-notice"><span>Controller: View switches Desktop/Game. Desktop: stick moves, A clicks, B goes back, X right-clicks, Y types, Start enters, D-pad navigates, right stick scrolls. Press both sticks for 7BZ Home.</span><span>Ctrl+Shift+H: hide bar</span></div>
      </div>
    </div>
    <button class="seven-reveal" data-action="show" aria-label="Show 7BZ top bar" title="Show 7BZ top bar">Show 7BZ ▾</button>
    <div class="seven-toast" role="status"></div>`;
  document.body.appendChild(hud);
  const keyboard = document.createElement("div");
  keyboard.id = "seven-controller-keyboard";
  keyboard.setAttribute("aria-label", "Controller on-screen keyboard");
  keyboard.innerHTML = '<div class="seven-keyboard-heading">On-screen keyboard · D-pad select · A type · X delete · Start enter · B close</div><div class="seven-keyboard-grid"></div>';
  document.body.appendChild(keyboard);
  hud.classList.toggle("is-hidden", state.hidden);

  const one = (selector) => hud.querySelector(selector);
  const stat = (name, text) => { const target = one(`[data-stat="${name}"]`); if (target) target.textContent = text; };
  const button = (name) => one(`[data-action="${name}"]`);
  const toast = (message) => {
    const target = one(".seven-toast");
    target.textContent = message;
    target.classList.add("is-visible");
    clearTimeout(state.toastTimer);
    state.toastTimer = setTimeout(() => target.classList.remove("is-visible"), 3200);
  };

  function controlBase() {
    const replaced = window.location.pathname.replace(/\/proxy\/(?:8080|8081)(?:\/.*)?$/, "/proxy/8766");
    return replaced === window.location.pathname ? "/proxy/8766" : replaced;
  }

  async function controllerSend(payload, quiet = false) {
    try {
      const response = await fetch(`${controlBase()}/controller`, {
        method: "POST", credentials: "same-origin",
        headers: { "X-7BZ-Action": "hud", "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
    } catch (error) {
      if (!quiet || Date.now() - state.controllerErrorAt > 10000) {
        toast(`Controller input unavailable: ${error.message}`);
        state.controllerErrorAt = Date.now();
      }
    }
  }

  const letters = "abcdefghijklmnopqrstuvwxyz0123456789.,/-_@:'?!".split("");
  const keyboardKeys = [...letters, "Space", "Backspace", "Enter"];
  function drawKeyboard() {
    const grid = keyboard.querySelector(".seven-keyboard-grid");
    grid.replaceChildren();
    keyboardKeys.forEach((key, index) => {
      const cell = document.createElement("button");
      cell.type = "button";
      cell.textContent = state.shifted && key.length === 1 ? key.toUpperCase() : key;
      cell.className = "seven-keyboard-key" + (index === state.keyIndex ? " is-selected" : "");
      cell.addEventListener("click", () => { state.keyIndex = index; typeSelected(); });
      grid.appendChild(cell);
    });
  }
  function showKeyboard(open) {
    if (open && state.controllerMode !== "desktop") setControllerMode("desktop");
    state.keyboardOpen = open;
    keyboard.classList.toggle("is-open", open);
    if (open) drawKeyboard();
  }
  function typeSelected() {
    const key = keyboardKeys[state.keyIndex];
    if (key === "Space") controllerSend({ action: "key", key: "space" });
    else if (key === "Backspace") controllerSend({ action: "key", key: "BackSpace" });
    else if (key === "Enter") controllerSend({ action: "key", key: "Return" });
    else controllerSend({ action: "text", text: state.shifted ? key.toUpperCase() : key });
  }
  function setControllerMode(mode) {
    state.controllerMode = mode;
    if (mode === "game") showKeyboard(false);
    post({ type: "gamepadControl", enabled: mode === "game" });
    button("controller").textContent = mode === "desktop" ? "🎮 Desktop Cursor" : "🎮 Game Input";
    button("controller").classList.toggle("is-active", mode === "desktop");
    toast(mode === "desktop" ? "Controller controls desktop. View switches to game input." : "Controller controls game. View returns to desktop.");
  }
  function padAxis(value) { return Math.abs(value || 0) > .18 ? value : 0; }
  function controllerFrame(now) {
    const pad = navigator.getGamepads ? Array.from(navigator.getGamepads()).find(Boolean) : null;
    if (pad) {
      const pressed = (index) => Boolean(pad.buttons[index]?.pressed);
      const edge = (index) => pressed(index) && !state.padButtons[index];
      if (edge(8)) setControllerMode(state.controllerMode === "desktop" ? "game" : "desktop");
      if (state.controllerMode === "desktop") {
        if (edge(10) && pressed(11) || edge(11) && pressed(10)) controllerSend({ action: "home" });
        if (edge(3)) showKeyboard(!state.keyboardOpen);
        if (state.keyboardOpen) {
          if (edge(1)) showKeyboard(false);
          if (edge(2)) controllerSend({ action: "key", key: "BackSpace" });
          if (edge(9)) controllerSend({ action: "key", key: "Return" });
          if (edge(4) || edge(5)) { state.shifted = !state.shifted; drawKeyboard(); }
          const columns = 10;
          if (edge(12)) state.keyIndex = Math.max(0, state.keyIndex - columns);
          if (edge(13)) state.keyIndex = Math.min(keyboardKeys.length - 1, state.keyIndex + columns);
          if (edge(14)) state.keyIndex = Math.max(0, state.keyIndex - 1);
          if (edge(15)) state.keyIndex = Math.min(keyboardKeys.length - 1, state.keyIndex + 1);
          if ([12, 13, 14, 15].some(edge)) drawKeyboard();
          if (edge(0)) typeSelected();
        } else {
          if (edge(0)) controllerSend({ action: "click", button: 1 });
          if (edge(1)) controllerSend({ action: "key", key: "Escape" });
          if (edge(2)) controllerSend({ action: "click", button: 3 });
          if (edge(9)) controllerSend({ action: "key", key: "Return" });
          for (const [index, key] of [[12, "Up"], [13, "Down"], [14, "Left"], [15, "Right"]]) {
            if (edge(index)) controllerSend({ action: "key", key });
          }
          if (edge(4)) controllerSend({ action: "key", key: "Tab" });
          if (edge(5)) controllerSend({ action: "key", key: "Return" });
          const dx = padAxis(pad.axes[0]), dy = padAxis(pad.axes[1]);
          if ((dx || dy) && now - state.lastMove > 50 && !state.controllerBusy) {
            state.lastMove = now;
            state.cursorX = Math.max(0, Math.min(1, state.cursorX + dx * .018));
            state.cursorY = Math.max(0, Math.min(1, state.cursorY + dy * .025));
            state.controllerBusy = true;
            controllerSend({ action: "move", x: state.cursorX, y: state.cursorY }, true)
              .finally(() => { state.controllerBusy = false; });
          }
          const scroll = padAxis(pad.axes[3]);
          if (scroll && now - state.lastScroll > 130) {
            state.lastScroll = now;
            controllerSend({ action: "scroll", direction: scroll < 0 ? "up" : "down" }, true);
          }
        }
      }
      state.padButtons = pad.buttons.map((item) => Boolean(item.pressed));
    } else state.padButtons = [];
    requestAnimationFrame(controllerFrame);
  }

  function checkGamepads() {
    try {
      const pads = navigator.getGamepads ? Array.from(navigator.getGamepads()).filter(Boolean) : [];
      if (pads.length > 0) {
        const p = pads[0];
        const name = p.id ? p.id.split("(")[0].trim() : "Controller";
        stat("pad", name.slice(0, 11) || "Connected");
        if (!state.hasGamepad) {
          state.hasGamepad = true;
          toast(`🎮 Controller Connected: ${name.slice(0, 25)}`);
          setControllerMode("desktop");
        }
      } else {
        stat("pad", "None");
        state.hasGamepad = false;
      }
    } catch (_) {}
  }

  function current() {
    const latest = window.stream_stats?.latest || {};
    const client = window.stream_client || {};
    const rtt = value(latest.rtt_ms);
    if (rtt > 0) {
      state.rtts.push(rtt);
      if (state.rtts.length > 14) state.rtts.shift();
    }
    const mean = state.rtts.reduce((sum, item) => sum + item, 0) / Math.max(1, state.rtts.length);
    const jitter = Math.sqrt(state.rtts.reduce((sum, item) => sum + ((item - mean) ** 2), 0) / Math.max(1, state.rtts.length));
    const lost = value(latest.lost_frames ?? latest.frames_not_shown);
    return {
      latest, client, rtt, jitter, lost,
      fps: value(latest.fps, value(window.fps)),
      rate: value(latest.video_mbps, value(latest.mbps)),
    };
  }

  let lastGpuCheck = 0;
  async function syncGpus() {
    const now = Date.now();
    if (now - lastGpuCheck < 2000) return;
    lastGpuCheck = now;
    try {
      const response = await fetch(`${controlBase()}/gpus`, { credentials: "same-origin" });
      if (response.ok) {
        const data = await response.json();
        const gpus = data.gpus || [];
        if (gpus.length >= 2) {
          const g0 = gpus[0], g1 = gpus[1];
          stat("gpu", `${g0.utilization}% | ${g1.utilization}%`);
          stat("gpu0_metric", `${g0.utilization}% · ${(g0.memory_used / 1024).toFixed(1)} GB`);
          stat("gpu1_metric", `${g1.utilization}% · ${(g1.memory_used / 1024).toFixed(1)} GB`);
        } else if (gpus.length === 1) {
          const g0 = gpus[0];
          stat("gpu", `${g0.utilization}%`);
          stat("gpu0_metric", `${g0.utilization}% · ${(g0.memory_used / 1024).toFixed(1)} GB`);
          stat("gpu1_metric", "Inactive");
        }
      }
    } catch (_) {}
  }

  function render() {
    const sample = current();
    const latest = sample.latest;
    stat("fps", sample.fps ? `${format(sample.fps)} FPS` : "--");
    stat("rtt", sample.rtt ? `${format(sample.rtt)} ms` : "--");
    stat("rate", sample.rate ? `${format(sample.rate, 1)} Mbps` : "--");
    if (!lastGpuCheck) {
      stat("gpu", latest.gpu_percent !== undefined ? `${format(latest.gpu_percent)}%` : "--");
    }
    stat("cpu", latest.cpu_percent !== undefined ? `${format(latest.cpu_percent)}%` : "--");
    stat("jitter", state.rtts.length > 2 ? `${format(sample.jitter, 1)} ms` : "--");
    stat("loss", Number.isFinite(Number(sample.lost)) ? String(sample.lost) : "--");
    const used = value(latest.gpu_mem_used), total = value(latest.gpu_mem_total);
    const gib = 1024 ** 3;
    if (!lastGpuCheck && total) {
      stat("gpu0_metric", `${format(used / gib, 1)} / ${format(total / gib, 1)} GB`);
    }
    const transport = sample.client.transport || window.__SELKIES_STREAMING_MODE__ ||
      document.getElementById("streamModeSelect")?.value || "websockets";
    stat("transport", transport === "webrtc" ? "WebRTC" : "WebSocket");
    stat("packet", transport === "webrtc" && latest.packet_loss_percent !== undefined
      ? `${format(latest.packet_loss_percent, 2)}%` : "N/A (WS)");
    checkGamepads();
    syncGpus();
  }

  function toggleExpanded() {
    state.expanded = !state.expanded;
    one(".seven-details").classList.toggle("is-collapsed", !state.expanded);
    button("expand").textContent = state.expanded ? "⌃" : "⌄";
    post({ type: "statsOpen", open: true });
  }

  function setHidden(hidden) {
    state.hidden = hidden;
    hud.classList.toggle("is-hidden", hidden);
    try { localStorage.setItem("sevenBzHudHidden", hidden ? "1" : "0"); } catch (_) {}
  }

  function togglePointer() {
    // Selkies owns fullscreen, pointer lock, and the relative-motion handler.
    // A second requestPointerLock from this HUD can steal its input target.
    post({ type: "requestGamingMode" });
    toast("Gaming Mode requested. Press Esc to exit.");
  }

  async function toggleInputMode() {
    const btn = button("mode");
    if (!btn) return;
    btn.disabled = true;
    try {
      const response = await fetch(`${controlBase()}/input-mode`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-7BZ-Action": "hud", "Content-Type": "application/json" },
        body: JSON.stringify({})
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const result = await response.json();
      state.inputMode = result.mode;
      updateInputModeUI();
      toast(result.mode === "mouse_keyboard"
        ? "Mouse & Keyboard selected. Restart the game to remove virtual controllers."
        : "Gamepad selected. Restart the game to expose Xbox controllers.");
    } catch (error) {
      toast(`Input mode switch failed: ${error.message}`);
    } finally {
      btn.disabled = false;
    }
  }

  function updateInputModeUI() {
    const isKbm = state.inputMode === "mouse_keyboard";
    const label = isKbm ? "🖱️ Mode: M+K" : "🎮 Mode: Gamepad";
    stat("modename", label);
    const btn = button("mode");
    if (btn) {
      btn.textContent = label;
      btn.classList.toggle("is-active", !isKbm);
    }
  }

  async function syncInputMode() {
    try {
      const response = await fetch(`${controlBase()}/input-mode`, { credentials: "same-origin" });
      if (response.ok) {
        const data = await response.json();
        state.inputMode = data.mode || "mouse_keyboard";
        updateInputModeUI();
      }
    } catch (_) {}
  }

  async function toggleEsc() {
    if (!navigator.keyboard?.lock) { toast("Esc Lock requires a Chromium browser in fullscreen."); return; }
    try {
      if (state.esc) { navigator.keyboard.unlock(); state.esc = false; }
      else { await navigator.keyboard.lock(["Escape"]); state.esc = true; }
      button("esc").classList.toggle("is-active", state.esc);
      toast(state.esc ? "Escape is captured by the remote game." : "Escape lock released.");
    } catch (_error) { toast("Enter fullscreen first, then enable Esc Lock."); }
  }

  async function resetGame() {
    const control = button("reset");
    control.disabled = true;
    control.textContent = "Stopping…";
    try {
      const response = await fetch(`${controlBase()}/reset`, { method: "POST", credentials: "same-origin",
        headers: { "X-7BZ-Action": "hud" } });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const result = await response.json();
      toast(result.message || "Dashboard restored.");
      if (document.pointerLockElement) document.exitPointerLock();
    } catch (error) { toast(`Reset failed: ${error.message}`); }
    finally { control.disabled = false; control.textContent = "Force Kill / Exit Frozen Game"; }
  }

  hud.addEventListener("click", (event) => {
    const action = event.target.closest("[data-action]")?.dataset.action;
    if (!action) return;
    if (action === "hide") setHidden(true);
    if (action === "show") setHidden(false);
    if (action === "expand") toggleExpanded();
    if (action === "fullscreen") post({ type: "requestFullscreen" });
    if (action === "pointer") togglePointer();
    if (action === "mode") toggleInputMode();
    if (action === "controller") setControllerMode(state.controllerMode === "desktop" ? "game" : "desktop");
    if (action === "keyboard") showKeyboard(!state.keyboardOpen);
    if (action === "home") controllerSend({ action: "home" });
    if (action === "esc") toggleEsc();
    if (action === "audio") {
      state.audio = true;
      post({ type: "pipelineControl", pipeline: "audio", enabled: true });
      post({ type: "setMute", value: false });
      post({ type: "setVolume", value: 1 });
      button("audio").classList.add("is-active");
      toast("Audio enabled at full volume.");
    }
    if (action === "reset") resetGame();
  });

  document.addEventListener("pointerlockchange", () => {
    state.pointer = Boolean(document.pointerLockElement);
    button("pointer").classList.toggle("is-active", state.pointer);
  });
  window.addEventListener("message", (event) => {
    if (event.source !== window || event.origin !== window.location.origin) return;
    if (event.data?.type === "serverSettings" && !state.qualityInitialized) {
      // An earlier HUD saved 45 FPS and 4 Mbps in Selkies' browser storage.
      // Reset the chosen ceiling once, after the dashboard restores its settings.
      state.qualityInitialized = true;
      setTimeout(() => post({ type: "settings", settings: {
        rate_control_mode: "cbr", video_bitrate: 3000, framerate: 60,
      } }), 1500);
      return;
    }
    if (event.data?.type !== "gamingModeUpdate") return;
    state.pointer = Boolean(event.data.active);
    button("pointer").classList.toggle("is-active", state.pointer);
    if (state.pointer) toast("Gaming Mode active: relative mouse input enabled.");
  });
  document.addEventListener("fullscreenchange", () => button("fullscreen").classList.toggle("is-active", Boolean(document.fullscreenElement)));
  window.addEventListener("keydown", (event) => {
    if (event.ctrlKey && event.shiftKey && event.code === "KeyM") {
      event.preventDefault();
      toggleExpanded();
    }
    if (event.ctrlKey && event.shiftKey && event.code === "KeyH") {
      event.preventDefault();
      setHidden(!state.hidden);
    }
  }, true);

  window.addEventListener("gamepadconnected", (event) => {
    state.hasGamepad = true;
    toast(`🎮 Gamepad Connected: ${event.gamepad.id.slice(0, 30)}`);
    setControllerMode("desktop");
    checkGamepads();
  });
  window.addEventListener("gamepaddisconnected", () => {
    state.hasGamepad = false;
    toast("Gamepad disconnected");
    checkGamepads();
  });

  post({ type: "statsOpen", open: true });
  syncInputMode();
  setInterval(render, 1000);
  setTimeout(render, 700);
  requestAnimationFrame(controllerFrame);
})();
