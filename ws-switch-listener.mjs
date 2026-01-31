#!/usr/bin/env node
/**
 * Evon Physical Switch/Button Event Listener
 *
 * Attempts to detect physical wall button presses (Taster) via WebSocket.
 *
 * FINDINGS (Negative):
 * - Physical switches (Base.bSwitchUniversal) do NOT expose press events
 * - They only have static config: ID, Name, Address, Channel, Line
 * - No Pressed, State, Value, or similar properties exist
 * - Button presses are handled internally by the Evon controller
 *
 * WORKAROUND:
 * - Monitor the devices that buttons control (lights, blinds, etc.)
 * - When a light state changes without API call, a button was likely pressed
 *
 * NOTE: For doorbell/intercom events, use ws-security-door.mjs instead!
 * The Intercom2N1000.DoorSwitch DOES expose real-time state.
 *
 * Usage:
 *   EVON_TOKEN="your-jwt-token" node ws-switch-listener.mjs [mode]
 *   Modes: lights (default), switches, all
 *
 * See docs/WEBSOCKET_API.md for full API documentation.
 */

import { WebSocket } from 'ws';
import { config } from 'dotenv';

config();

const EVON_HOST = process.env.EVON_HOST || 'http://192.168.1.4';
const WS_HOST = EVON_HOST.replace('http://', 'ws://').replace('https://', 'wss://');
const TOKEN = process.env.EVON_TOKEN;

// Configuration
const TIMEOUT_SECONDS = 120;  // How long to listen
const MONITOR_MODE = process.argv[2] || 'lights';  // 'lights', 'switches', or 'all'

if (!TOKEN) {
  console.error('Error: EVON_TOKEN environment variable required');
  console.error('');
  console.error('To get a token:');
  console.error('  1. Open Evon web interface in browser');
  console.error('  2. Open Developer Tools > Application > Cookies');
  console.error('  3. Copy the "token" cookie value');
  console.error('');
  console.error('Usage: EVON_TOKEN="your-token" node ws-switch-listener.mjs [mode]');
  console.error('Modes: lights, switches, all');
  process.exit(1);
}

let sequenceId = 1;

function send(ws, methodName, args) {
  const seq = sequenceId++;
  ws.send(JSON.stringify({
    methodName: "CallWithReturn",
    request: { args, methodName, sequenceId: seq }
  }));
  return seq;
}

async function main() {
  console.log('╔════════════════════════════════════════════════════════════╗');
  console.log('║         Evon Switch/Button Event Listener                  ║');
  console.log('╚════════════════════════════════════════════════════════════╝');
  console.log('');
  console.log(`Mode: ${MONITOR_MODE}`);
  console.log(`Timeout: ${TIMEOUT_SECONDS} seconds`);
  console.log(`Connecting to ${WS_HOST}...`);
  console.log('');

  const ws = new WebSocket(WS_HOST, 'echo-protocol', {
    headers: {
      'Origin': EVON_HOST,
      'Cookie': `token=${TOKEN}; x-elocs-isrelay=false; x-elocs-token_in_cookie_only=0`,
    }
  });

  const deviceNames = new Map();
  const switchToLight = new Map();  // Map switch IDs to their controlled lights

  ws.on('open', () => {
    console.log('✓ Connected!\n');

    // Get all switches first
    send(ws, 'GetInstances', ['Base.bSwitchUniversal']);

    // Get all lights
    setTimeout(() => send(ws, 'GetInstances', ['Base.bLight']), 200);
  });

  ws.on('message', (data) => {
    try {
      const msg = JSON.parse(data.toString());
      const [type, payload] = msg;
      const time = new Date().toLocaleTimeString();

      // Skip connection and user data messages
      if (type === 'Connected') {
        return;
      }
      if (type === 'Event' && payload?.methodName === 'UserDataChanged') {
        return;
      }

      // Handle GetInstances response
      if (type === 'Callback' && payload?.methodName === 'GetInstances') {
        const result = payload.args?.[0] || [];
        const devices = result.filter(d => d.Name && d.ID && !d.ID.startsWith('Base.') && !d.ID.startsWith('SmartCOM.'));

        // Check if these are switches or lights
        const isSwitches = devices.some(d => d.ID?.includes('Input') || d.ID?.includes('Switch'));
        const isLights = devices.some(d => d.ID?.includes('Light'));

        if (isSwitches) {
          console.log(`Found ${devices.length} switches:`);
          devices.forEach(d => {
            deviceNames.set(d.ID, d.Name);
            console.log(`  ${d.ID}: ${d.Name}`);

            // Try to map switch to light (simple pattern matching)
            const match = d.ID.match(/SC\d+_M(\d+)\.Input(\d+)/);
            if (match) {
              const lightId = `SC1_M0${match[1]}.Light${match[2]}`;
              switchToLight.set(d.ID, lightId);
            }
          });
          console.log('');

          // Subscribe to switch properties if in 'switches' or 'all' mode
          if (MONITOR_MODE === 'switches' || MONITOR_MODE === 'all') {
            console.log('Subscribing to switch properties...');
            const switchSubs = devices.map(d => ({
              Instanceid: d.ID,
              // Try ALL possible property names
              Properties: [
                'State', 'Value', 'Pressed', 'Released', 'Active', 'On',
                'LongPressed', 'ShortPressed', 'DoublePressed', 'Click',
                'IsPressed', 'WasPressed', 'ButtonState', 'InputState',
                'LastPressed', 'LastEvent', 'Event', 'Action', 'Trigger',
                'Counter', 'PressCount', 'ClickCount'
              ]
            }));
            send(ws, 'RegisterValuesChanged', [true, switchSubs, true, true]);
          }
        }

        if (isLights) {
          console.log(`Found ${devices.length} lights:`);
          devices.forEach(d => {
            deviceNames.set(d.ID, d.Name);
            console.log(`  ${d.ID}: ${d.Name}`);
          });
          console.log('');

          // Subscribe to light properties if in 'lights' or 'all' mode
          if (MONITOR_MODE === 'lights' || MONITOR_MODE === 'all') {
            console.log('Subscribing to light state changes...');
            const lightSubs = devices.map(d => ({
              Instanceid: d.ID,
              Properties: ['IsOn', 'DirectOn', 'Brightness', 'ScaledBrightness']
            }));
            send(ws, 'RegisterValuesChanged', [true, lightSubs, true, true]);
          }

          // Start listening
          setTimeout(() => {
            console.log('');
            console.log('═'.repeat(60));
            console.log('Listening for events... Press any Taster/switch!');
            console.log('═'.repeat(60));
            console.log('');
          }, 500);
        }

        return;
      }

      // Handle ValuesChanged events - this is where we detect changes
      if (type === 'Event' && payload?.methodName === 'ValuesChanged') {
        const table = payload.args?.[0]?.table || {};
        const changes = [];

        for (const [key, entry] of Object.entries(table)) {
          const parts = key.split('.');
          const prop = parts.pop();
          const instanceId = parts.join('.');
          const value = entry.value?.Value;
          const name = deviceNames.get(instanceId) || instanceId;

          // Skip initial value loads (only show actual changes)
          if (entry.value?.SetReason === 'Init') continue;

          changes.push({ instanceId, name, prop, value });
        }

        if (changes.length > 0) {
          console.log(`[${time}] ════════════════════════════════════════`);
          changes.forEach(({ instanceId, name, prop, value }) => {
            // Check if this light change might be from a switch
            const possibleSwitch = [...switchToLight.entries()]
              .find(([sw, lt]) => lt === instanceId);

            if (possibleSwitch) {
              console.log(`  📍 ${name} (${instanceId})`);
              console.log(`     ${prop} = ${JSON.stringify(value)}`);
              console.log(`     Possible trigger: ${deviceNames.get(possibleSwitch[0]) || possibleSwitch[0]}`);
            } else if (instanceId.includes('Input') || instanceId.includes('Switch')) {
              // Direct switch property change (unlikely but worth capturing)
              console.log(`  🔘 SWITCH EVENT: ${name}`);
              console.log(`     ${prop} = ${JSON.stringify(value)}`);
            } else {
              console.log(`  💡 ${name}: ${prop} = ${JSON.stringify(value)}`);
            }
          });
          console.log('');
        }
        return;
      }

      // Log any other events (might help discover new event types)
      if (type === 'Event') {
        const methodName = payload?.methodName;
        console.log(`[${time}] Unknown Event: ${methodName}`);
        console.log(`  ${JSON.stringify(payload).slice(0, 200)}`);
        console.log('');
        return;
      }

      // Skip callback confirmations
      if (type === 'Callback') {
        return;
      }

      // Log anything unexpected
      console.log(`[${time}] ${type}: ${JSON.stringify(msg).slice(0, 100)}`);

    } catch (e) {
      console.error('Parse error:', e.message);
    }
  });

  ws.on('error', (e) => {
    console.error('WebSocket error:', e.message);
  });

  ws.on('close', (code, reason) => {
    console.log(`\nConnection closed (code: ${code})`);
    process.exit(0);
  });

  // Auto-close after timeout
  setTimeout(() => {
    console.log(`\n⏱️  Timeout after ${TIMEOUT_SECONDS} seconds`);
    ws.close();
  }, TIMEOUT_SECONDS * 1000);

  // Handle Ctrl+C gracefully
  process.on('SIGINT', () => {
    console.log('\n\nStopping...');
    ws.close();
  });
}

main().catch(console.error);
