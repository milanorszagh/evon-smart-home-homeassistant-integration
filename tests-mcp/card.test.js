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
