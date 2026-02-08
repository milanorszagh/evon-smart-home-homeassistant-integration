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
    const needsRender =
      !this._initialized ||
      isRecording !== this._lastRecordingState ||
      recordingsJson !== this._lastRecordingsJson;

    this._lastRecordingState = isRecording;
    this._lastRecordingsJson = recordingsJson;

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

  disconnectedCallback() {
    this._stopStopwatch();
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

        .record-row { display: flex; align-items: center; gap: 12px; padding: 8px 16px; }
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
        .record-btn ha-icon { --mdc-icon-size: 20px; }
        .record-btn.recording ha-icon { animation: pulse 1.2s ease-in-out infinite; }
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

      <div class="separator">
        <ha-icon icon="mdi:record-circle"></ha-icon>
        <span>Recording</span>
      </div>

      <div class="record-row">
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
  description: "Recording controls and history for Evon cameras",
});
