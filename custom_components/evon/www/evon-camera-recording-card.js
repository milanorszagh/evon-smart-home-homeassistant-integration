// How long the "Open door" button shows its "Opening…" state after a press.
// The door release pulse itself is configured in the integration options.
const DOOR_FEEDBACK_MS = 3000;

class EvonCameraRecordingCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
    this._expandedVideo = null;
    this._resolvedUrl = null;
    this._stopwatchSeconds = 0;
    this._stopwatchInterval = null;
    this._lastRecordingState = null;
    this._lastRecordingsJson = null;
    this._lastDoorAvailable = null;
    this._doorOpening = false;
    this._doorTimeout = null;
    this._initialized = false;
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error("entity is required");
    }
    this._config = config;
  }

  set hass(hass) {
    const oldHass = this._hass;
    this._hass = hass;
    if (!this._config) return;

    const entityId = this._config.entity;
    const state = hass.states[entityId];
    if (!state) return;

    const isRecording = state.attributes.recording === true;
    const wasRecording =
      oldHass &&
      oldHass.states[entityId] &&
      oldHass.states[entityId].attributes.recording === true;

    if (isRecording && !wasRecording) {
      this._startStopwatch(state.attributes.recording_duration || 0);
    } else if (!isRecording && wasRecording) {
      this._stopStopwatch();
    }

    // Skip full re-render if video is playing and nothing relevant changed
    const recordingsJson = JSON.stringify(
      state.attributes.recent_recordings || []
    );
    const doorAvailable = this._doorAvailable(hass);
    const needsRender =
      !this._initialized ||
      isRecording !== this._lastRecordingState ||
      recordingsJson !== this._lastRecordingsJson ||
      doorAvailable !== this._lastDoorAvailable;

    this._lastRecordingState = isRecording;
    this._lastRecordingsJson = recordingsJson;
    this._lastDoorAvailable = doorAvailable;

    if (needsRender) {
      this._render();
    }
  }

  _startStopwatch(initialSeconds) {
    this._stopStopwatch();
    this._stopwatchSeconds = Math.floor(initialSeconds);
    this._stopwatchInterval = setInterval(() => {
      this._stopwatchSeconds++;
      this._updateStopwatchDisplay();
    }, 1000);
  }

  _stopStopwatch() {
    if (this._stopwatchInterval) {
      clearInterval(this._stopwatchInterval);
      this._stopwatchInterval = null;
    }
    this._stopwatchSeconds = 0;
  }

  _updateStopwatchDisplay() {
    const el = this.shadowRoot.querySelector(".stopwatch");
    if (el) el.textContent = this._formatTime(this._stopwatchSeconds);
  }

  _formatTime(seconds) {
    const m = String(Math.floor(seconds / 60)).padStart(2, "0");
    const s = String(seconds % 60).padStart(2, "0");
    return `${m}:${s}`;
  }

  connectedCallback() {
    // Register here (not in set hass) so the Talk button tracks call state
    // whenever the card enters the DOM, e.g. when the door popup is opened.
    if (!this._onSipUpdate) {
      this._onSipUpdate = () => this._updateTalkButton();
      window.addEventListener("sipcore-update", this._onSipUpdate);
      window.addEventListener("sipcore-call-started", this._onSipUpdate);
      window.addEventListener("sipcore-call-ended", this._onSipUpdate);
    }
    // Reflect any already-active/incoming call the moment the popup opens.
    this._updateTalkButton();
  }

  disconnectedCallback() {
    this._stopStopwatch();
    // The pulse was already sent; cancelling the feedback timer must also end the
    // "Opening…" state, otherwise a re-attached card (popup reopened, view switched)
    // stays stuck and ignores every later press.
    if (this._doorTimeout) this._setDoorOpening(false);
    if (this._onSipUpdate) {
      window.removeEventListener("sipcore-update", this._onSipUpdate);
      window.removeEventListener("sipcore-call-started", this._onSipUpdate);
      window.removeEventListener("sipcore-call-ended", this._onSipUpdate);
      this._onSipUpdate = null;
    }
  }

  // Optional "Open door" button (config: door_button), e.g. the integration's
  // button.<intercom>_open_door entity. Pressing it pulses the door release.
  _doorAvailable(hass) {
    const entityId = this._config && this._config.door_button;
    if (!entityId) return false;
    const state = hass.states[entityId];
    return !!state && state.state !== "unavailable";
  }

  _clearDoorTimeout() {
    if (this._doorTimeout) {
      clearTimeout(this._doorTimeout);
      this._doorTimeout = null;
    }
  }

  async _openDoor() {
    if (!this._hass || !this._config) return;
    const entityId = this._config.door_button;
    if (!entityId || !this._doorAvailable(this._hass)) return;
    if (this._doorOpening) return; // ignore double taps while the pulse runs
    this._setDoorOpening(true);
    try {
      await this._hass.callService("button", "press", { entity_id: entityId });
    } catch (e) {
      console.error("Failed to open door:", e);
      this._setDoorOpening(false);
      return;
    }
    this._doorTimeout = setTimeout(() => this._setDoorOpening(false), DOOR_FEEDBACK_MS);
  }

  // Optional "Talk" button (config: sip_extension). Starts a SIP call to the door
  // extension via the SIP Core engine; the SIP Core popup then shows the live call.
  // State of the SIP engine: "unavailable" | "idle" | "incoming" | "outgoing"
  // | "connecting" | "connected".
  _talkState() {
    const sip = window.sipCore;
    if (!sip || typeof sip.startCall !== "function") return "unavailable";
    return sip.callState || "idle";
  }

  _talkLabel(s) {
    if (s === "incoming") return "Answer";
    if (s === "outgoing" || s === "connecting") return "Calling\u2026";
    if (s === "connected") return "Hang up";
    return "Talk";
  }

  _talkIcon(s) {
    if (s === "incoming") return "mdi:phone-ring";
    if (s === "outgoing" || s === "connecting") return "mdi:phone-outgoing";
    if (s === "connected") return "mdi:phone-hangup";
    return "mdi:phone-in-talk";
  }

  // Click: answer an incoming call, hang up an active one, else start the
  // outbound call to the door extension. The SIP Core popup shows the live call.
  _talk() {
    const sip = window.sipCore;
    if (!sip || typeof sip.startCall !== "function") {
      console.error("SIP Core not available. Open HA via the HTTPS (Tailscale) URL and ensure the SIP Core integration is set up.");
      return;
    }
    const s = sip.callState;
    try {
      if (s === "incoming") sip.answerCall();
      else if (!s || s === "idle") sip.startCall(String(this._config.sip_extension || ""));
      else sip.endCall();
    } catch (e) {
      console.error("SIP call action failed:", e);
    }
  }

  // Live-update the Talk button in place when the SIP engine state changes
  // (so an incoming call turns it into "Answer" without a full re-render).
  _updateTalkButton() {
    const btn = this.shadowRoot && this.shadowRoot.querySelector("#talk-btn");
    if (!btn) return;
    const s = this._talkState();
    btn.className = `record-btn talk-btn ${s}`;
    const ic = btn.querySelector("ha-icon");
    if (ic) ic.setAttribute("icon", this._talkIcon(s));
    const sp = btn.querySelector("span");
    if (sp) sp.textContent = this._talkLabel(s);
  }

  // Updates the door button in place (no full re-render, so an inline video keeps playing).
  _setDoorOpening(opening) {
    this._clearDoorTimeout();
    this._doorOpening = opening;
    const btn = this.shadowRoot.querySelector("#door-btn");
    if (!btn) return;
    btn.classList.toggle("opening", opening);
    btn.querySelector("ha-icon").setAttribute("icon", this._doorIcon(opening));
    btn.querySelector("span").textContent = this._doorLabel(opening);
  }

  _doorIcon(opening) {
    return opening ? "mdi:lock-open-variant-outline" : "mdi:door-open";
  }

  _doorLabel(opening) {
    return opening ? "Opening…" : "Open door";
  }

  _toggleRecording() {
    if (!this._hass || !this._config) return;
    const switchEntity =
      this._config.recording_switch ||
      this._config.entity.replace("camera.", "switch.") + "_recording";
    const switchState = this._hass.states[switchEntity];
    if (!switchState) return;
    const service = switchState.state === "on" ? "turn_off" : "turn_on";
    this._hass.callService("switch", service, { entity_id: switchEntity });
  }

  async _toggleVideo(url) {
    if (this._expandedVideo === url) {
      this._expandedVideo = null;
      this._resolvedUrl = null;
    } else {
      this._expandedVideo = url;
      this._resolvedUrl = null;
      try {
        const signed = await this._hass.callWS({
          type: "auth/sign_path",
          path: url,
          expires: 300,
        });
        this._resolvedUrl = signed.path;
      } catch (e) {
        console.error("Failed to sign URL:", e);
        this._resolvedUrl = null;
      }
    }
    this._render();
  }

  _openMediaBrowser() {
    // Navigate to media browser, browsing the local evon_recordings folder
    history.pushState(null, "", "/media-browser/browser/media-source%3A%2F%2Fmedia_source%2Flocal%2Fevon_recordings");
    window.dispatchEvent(new Event("location-changed"));
  }

  _render() {
    if (!this._hass || !this._config) return;
    this._initialized = true;

    const entityId = this._config.entity;
    const state = this._hass.states[entityId];
    if (!state) {
      this.shadowRoot.innerHTML = `<div style="padding:16px;text-align:center;color:var(--secondary-text-color)">Entity not found</div>`;
      return;
    }

    const isRecording = state.attributes.recording === true;
    const recordings = state.attributes.recent_recordings || [];
    const showTitle = this._config.show_title !== false;

    let doorHtml = "";
    if (this._config.door_button) {
      const available = this._doorAvailable(this._hass);
      const opening = this._doorOpening;
      doorHtml = `
        <button class="record-btn door-btn ${opening ? "opening" : ""}" id="door-btn"
          ${available ? "" : 'disabled title="Door button entity not found or unavailable"'}>
          <ha-icon icon="${this._doorIcon(opening)}"></ha-icon>
          <span>${this._doorLabel(opening)}</span>
        </button>`;
    }

    let talkHtml = "";
    if (this._config.sip_extension) {
      const ts = this._talkState();
      talkHtml = `
        <button class="record-btn talk-btn ${ts}" id="talk-btn">
          <ha-icon icon="${this._talkIcon(ts)}"></ha-icon>
          <span>${this._talkLabel(ts)}</span>
        </button>`;
    }

    let recordingsHtml = "";
    if (recordings.length > 0) {
      recordingsHtml = `<div class="recordings-list">${recordings
        .map(
          (rec, i) => `
        <div class="recording-item ${this._expandedVideo === rec.url ? "active" : ""}" data-url="${rec.url}" data-idx="${i}">
          <ha-icon icon="mdi:file-video-outline"></ha-icon>
          <div class="recording-info">
            <div class="recording-timestamp">${rec.timestamp}</div>
            <div class="recording-size">${rec.size}</div>
          </div>
          <ha-icon icon="${this._expandedVideo === rec.url ? "mdi:chevron-up" : "mdi:chevron-down"}"></ha-icon>
        </div>
        ${
          this._expandedVideo === rec.url && this._resolvedUrl
            ? `<div class="video-container"><video controls autoplay playsinline><source src="${this._resolvedUrl}" type="video/mp4"></video></div>`
            : ""
        }`
        )
        .join("")}</div>`;
    } else {
      recordingsHtml = `<div class="empty-state">No recordings yet</div>`;
    }

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; font-family: var(--ha-card-header-font-family, inherit); }

        .separator {
          display: flex; align-items: center; gap: 8px;
          padding: 12px 16px 4px;
          font-size: 14px; font-weight: 500;
          color: var(--primary-text-color); opacity: 0.8;
        }
        .separator ha-icon { --mdc-icon-size: 20px; color: var(--primary-text-color); opacity: 0.6; }

        .record-row { display: flex; flex-wrap: wrap; align-items: center; justify-content: center; gap: 12px 16px; padding: 8px 16px; }
        .record-row.no-title { padding-top: 12px; }
        .record-btn {
          display: flex; align-items: center; gap: 8px;
          padding: 8px 16px; border: none; border-radius: 12px; cursor: pointer;
          font-size: 14px; font-weight: 500; font-family: inherit;
          transition: all 0.2s ease;
          color: var(--primary-text-color);
          background: var(--card-background-color, rgba(255,255,255,0.05));
        }
        .record-btn:hover { filter: brightness(1.1); }
        .record-btn.recording { background: rgba(244,67,54,0.15); color: #f44336; }
        .record-btn:disabled { opacity: 0.4; cursor: not-allowed; }
        .record-btn:disabled:hover { filter: none; }
        .record-btn ha-icon { --mdc-icon-size: 20px; }
        .record-btn.recording ha-icon { animation: pulse 1.2s ease-in-out infinite; }
        .door-btn.opening { background: rgba(76,175,80,0.15); color: #4caf50; }
        .talk-btn ha-icon { color: #4caf50; }
        .talk-btn.incoming { background: rgba(76,175,80,0.15); color: #4caf50; }
        .talk-btn.incoming ha-icon { animation: pulse 1.2s ease-in-out infinite; }
        .talk-btn.connected { background: rgba(244,67,54,0.15); color: #f44336; }
        .talk-btn.connected ha-icon { color: #f44336; }
        .stopwatch {
          font-size: 15px; font-weight: 600; font-variant-numeric: tabular-nums;
          color: #f44336; min-width: 48px;
        }
        @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }

        .recordings-list { padding: 0 8px; }
        .recording-item {
          display: flex; align-items: center; gap: 10px;
          padding: 10px 8px; border-radius: 10px; cursor: pointer;
          transition: background 0.15s ease;
        }
        .recording-item:hover,
        .recording-item.active { background: var(--card-background-color, rgba(255,255,255,0.05)); }
        .recording-item ha-icon { --mdc-icon-size: 20px; color: var(--primary-text-color); opacity: 0.5; flex-shrink: 0; }
        .recording-info { flex: 1; min-width: 0; }
        .recording-timestamp { font-size: 13px; color: var(--primary-text-color); }
        .recording-size { font-size: 11px; color: var(--secondary-text-color); }

        .video-container { padding: 4px 16px 8px; }
        .video-container video { width: 100%; border-radius: 10px; background: #000; }

        .empty-state { padding: 16px; text-align: center; font-size: 13px; color: var(--secondary-text-color); opacity: 0.7; }

        .all-recordings { display: flex; align-items: center; justify-content: center; gap: 6px; padding: 10px 16px 14px; }
        .all-recordings-btn {
          display: flex; align-items: center; gap: 6px;
          font-size: 13px; color: var(--primary-color);
          padding: 6px 14px; border-radius: 10px; transition: background 0.15s ease;
          background: none; border: none; cursor: pointer; font-family: inherit;
        }
        .all-recordings-btn:hover { background: rgba(var(--rgb-primary-color, 66,133,244), 0.1); }
        .all-recordings-btn ha-icon { --mdc-icon-size: 16px; }
      </style>

      ${
        showTitle
          ? `<div class="separator">
        <ha-icon icon="mdi:record-circle"></ha-icon>
        <span>Recording</span>
      </div>`
          : ""
      }

      <div class="record-row ${showTitle ? "" : "no-title"}">
        ${doorHtml}
        ${talkHtml}
        <button class="record-btn ${isRecording ? "recording" : ""}" id="rec-btn">
          <ha-icon icon="${isRecording ? "mdi:stop" : "mdi:record-circle-outline"}"></ha-icon>
          ${isRecording ? "Stop" : "Record"}
        </button>
        ${isRecording ? `<span class="stopwatch">${this._formatTime(this._stopwatchSeconds)}</span>` : ""}
      </div>

      ${recordingsHtml}

      <div class="all-recordings">
        <button class="all-recordings-btn" id="all-rec-btn">
          <ha-icon icon="mdi:folder-play-outline"></ha-icon>
          All Recordings
        </button>
      </div>
    `;

    // Attach event listeners
    const doorBtn = this.shadowRoot.querySelector("#door-btn");
    if (doorBtn) doorBtn.addEventListener("click", () => this._openDoor());
    const talkBtn = this.shadowRoot.querySelector("#talk-btn");
    if (talkBtn) talkBtn.addEventListener("click", () => this._talk());
    this.shadowRoot
      .querySelector("#rec-btn")
      .addEventListener("click", () => this._toggleRecording());
    this.shadowRoot.querySelectorAll(".recording-item").forEach((el) => {
      el.addEventListener("click", () =>
        this._toggleVideo(el.dataset.url)
      );
    });
    this.shadowRoot
      .querySelector("#all-rec-btn")
      .addEventListener("click", () => this._openMediaBrowser());
  }

  getCardSize() {
    return 3;
  }
}

customElements.define("evon-camera-recording-card", EvonCameraRecordingCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "evon-camera-recording-card",
  name: "Evon Camera Recording",
  description: "Recording controls, history and an optional door-opener button for Evon cameras",
});

// Overlay badge for a live camera feed that shows the CURRENTLY SHOWN frame's
// capture time (24h HH:MM:SS) and its age ("Xs ago"), not the wall clock. It reads
// the camera entity's `image_last_updated` attribute (set by the Evon camera when a
// new frame arrives), so the time only changes when the picture changes and the age
// climbs if the feed freezes — a real liveness indicator. The age ticks every second
// while the frame time stays put between frames. Used as a picture-elements element:
//   { type: "custom:evon-live-clock", entity: "camera.xxx" }
// Shares this resource with the card, so no extra Lovelace resource is needed.
class EvonLiveClock extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  connectedCallback() {
    if (!this._root) {
      this._root = document.createElement("div");
      this._root.style.cssText =
        "background:rgba(0,0,0,0.55);color:#fff;padding:2px 7px;border-radius:6px;" +
        "font-size:12px;font-weight:600;font-variant-numeric:tabular-nums;" +
        "pointer-events:none;line-height:1.4;white-space:nowrap;" +
        "font-family:var(--ha-font-family-body,var(--mdc-typography-font-family,sans-serif));";
      this.appendChild(this._root);
    }
    this._render();
    // Tick the age every second; the frame time only changes when a new frame arrives.
    this._iv = setInterval(() => this._render(), 1000);
  }

  disconnectedCallback() {
    if (this._iv) clearInterval(this._iv);
    this._iv = null;
  }

  _frameDate() {
    const ent = this._config && this._config.entity;
    if (!ent || !this._hass || !this._hass.states[ent]) return null;
    const attrs = this._hass.states[ent].attributes || {};
    const iso = attrs.image_last_updated;
    if (!iso) return null;
    const d = new Date(iso);
    return isNaN(d.getTime()) ? null : d;
  }

  _render() {
    if (!this._root) return;
    const d = this._frameDate();
    if (!d) {
      this._root.textContent = "no frame";
      this._root.style.color = "#bbb";
      return;
    }
    const p = (n) => String(n).padStart(2, "0");
    const t = `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
    const age = Math.max(0, Math.round((Date.now() - d.getTime()) / 1000));
    const ageStr = age < 60 ? `${age}s` : `${Math.floor(age / 60)}m ${age % 60}s`;
    this._root.textContent = `${t} · ${ageStr} ago`;
    // White when fresh, amber after 5 s, red after 15 s.
    this._root.style.color = age <= 5 ? "#fff" : age <= 15 ? "#ffd54f" : "#ff8a80";
  }
}

if (!customElements.get("evon-live-clock")) {
  customElements.define("evon-live-clock", EvonLiveClock);
}
