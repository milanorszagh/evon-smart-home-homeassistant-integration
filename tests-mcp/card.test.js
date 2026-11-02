// Tests for the Lovelace card served by the HA integration
// (custom_components/evon/www/evon-camera-recording-card.js). The card is a plain
// browser script, so it is loaded into a VM context with minimal DOM stand-ins.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const CARD_PATH = new URL("../custom_components/evon/www/evon-camera-recording-card.js", import.meta.url);

function loadCard() {
  const defined = {};
  class FakeHTMLElement {
    attachShadow() {
      this.shadowRoot = { querySelector: () => null, innerHTML: "" };
      return this.shadowRoot;
    }
  }
  const ctx = {
    HTMLElement: FakeHTMLElement,
    customElements: {
      define: (name, cls) => (defined[name] = cls),
      get: (name) => defined[name],
    },
    addEventListener() {},
    removeEventListener() {},
    dispatchEvent() {},
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
    console,
  };
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext(readFileSync(CARD_PATH, "utf8"), ctx);
  return defined;
}

function doorCard(callService) {
  const Card = loadCard()["evon-camera-recording-card"];
  const card = new Card();
  card.setConfig({ entity: "camera.door", door_button: "button.door_open" });
  card._hass = { states: { "button.door_open": { state: "unknown" } }, callService };
  return card;
}

test("open-door press still works after the card is detached during the feedback window", async () => {
  let presses = 0;
  const card = doorCard(async () => {
    presses += 1;
  });

  await card._openDoor();
  assert.equal(presses, 1);

  // Popup closed / view switched within the 3 s "Opening…" window.
  card.disconnectedCallback();

  await card._openDoor();
  assert.equal(presses, 2, "a detached-and-reattached card must accept the next press");
  card.disconnectedCallback();
});

test("double tap during the feedback window is still ignored", async () => {
  let presses = 0;
  const card = doorCard(async () => {
    presses += 1;
  });

  await card._openDoor();
  await card._openDoor();

  assert.equal(presses, 1);
  card.disconnectedCallback();
});

test("recording metadata is HTML-escaped before it reaches innerHTML", () => {
  const Card = loadCard()["evon-camera-recording-card"];
  const card = new Card();
  card.shadowRoot = {
    innerHTML: "",
    querySelector: () => ({ addEventListener() {} }),
    querySelectorAll: () => [],
  };
  card.setConfig({ entity: "camera.door" });
  const evil = '/evon/recordings/Door_x" onmouseover="alert(1)" x=".mp4';
  card._expandedVideo = evil;
  card._resolvedUrl = '/signed"><img src=x onerror=alert(2)>';
  card._hass = {
    states: {
      "camera.door": {
        state: "idle",
        attributes: {
          recent_recordings: [{ url: evil, timestamp: "<script>alert(3)</script>", size: "<b>1 KB</b>" }],
        },
      },
    },
  };
  card._render();
  const html = card.shadowRoot.innerHTML;
  assert.ok(!html.includes("onmouseover="), "the URL must not be written into an attribute raw");
  assert.ok(!html.includes("<script>"), "the timestamp must be escaped");
  assert.ok(!html.includes("<b>1 KB</b>"), "the size must be escaped");
  assert.ok(!html.includes("<img src=x"), "the signed URL must be escaped");
  assert.ok(html.includes("&lt;script&gt;alert(3)&lt;/script&gt;"));
});
