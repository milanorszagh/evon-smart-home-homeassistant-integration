#!/usr/bin/env node
/**
 * Evon Security Door & Intercom Event Monitor
 *
 * Monitors Security.Door and Intercom devices via WebSocket for real-time events.
 * Unlike physical wall switches (Taster), security doors and intercoms DO expose
 * real-time state changes that can be subscribed to.
 *
 * FINDINGS:
 * - Door7586 (Eingangstür): IsOpen, DoorIsOpen, CallInProgress work!
 * - Intercom2N1000: DoorBellTriggered, DoorOpenTriggered, IsDoorOpen work!
 * - Intercom2N1000.DoorSwitch: IsOn (doorbell button pressed) works!
 *
 * Usage:
 *   node ws-security-door.mjs
 *
 * Test by:
 *   1. Ring the doorbell → DoorBellTriggered should change to true
 *   2. Open the entry door → IsOpen should change to true
 *   3. Start an intercom call → CallInProgress should change to true
 *
 * See docs/WEBSOCKET_API.md for full API documentation.
 */

import { WebSocket } from 'ws';
import { config } from 'dotenv';
import crypto from 'crypto';

config();

const EVON_HOST = process.env.EVON_HOST || 'http://192.168.1.4';
const WS_HOST = EVON_HOST.replace('http://', 'ws://').replace('https://', 'wss://');
const USERNAME = process.env.EVON_USERNAME;
const PASSWORD = process.env.EVON_PASSWORD;

const TIMEOUT_SECONDS = 120;

// Encode password the Evon way: Base64(SHA512(username + password))
function encodePassword(username, password) {
  const hash = crypto.createHash('sha512').update(username + password).digest();
  return hash.toString('base64');
}

// Get token via HTTP login
async function getToken() {
  // Check for manual token first
  if (process.env.EVON_TOKEN) {
    console.log('Using EVON_TOKEN from environment');
    return process.env.EVON_TOKEN;
  }

  if (!USERNAME || !PASSWORD) {
    console.error('Error: Need EVON_USERNAME and EVON_PASSWORD in .env, or set EVON_TOKEN');
    process.exit(1);
  }

  console.log(`Authenticating as ${USERNAME}...`);
  const encodedPassword = encodePassword(USERNAME, PASSWORD);

  const response = await fetch(`${EVON_HOST}/login`, {
    method: 'POST',
    headers: {
      'x-elocs-username': USERNAME,
      'x-elocs-password': encodedPassword,
    },
  });

  const token = response.headers.get('x-elocs-token');
  if (!token) {
    console.error('Login failed - no token received');
    console.error('Status:', response.status);
    console.error('Try setting EVON_TOKEN manually from browser cookies');
    process.exit(1);
  }

  console.log('✓ Authentication successful\n');
  return token;
}

let sequenceId = 1;
const pendingCallbacks = new Map();

function send(ws, methodName, args) {
  const seq = sequenceId++;
  ws.send(JSON.stringify({
    methodName: "CallWithReturn",
    request: { args, methodName, sequenceId: seq }
  }));
  return seq;
}

function sendAndWait(ws, methodName, args) {
  return new Promise((resolve) => {
    const seq = send(ws, methodName, args);
    pendingCallbacks.set(seq, resolve);
  });
}

async function main() {
  console.log('╔════════════════════════════════════════════════════════════╗');
  console.log('║         Evon Security Door Explorer                        ║');
  console.log('╚════════════════════════════════════════════════════════════╝');
  console.log('');

  const token = await getToken();

  console.log(`Connecting to ${WS_HOST}...`);
  console.log('');

  const ws = new WebSocket(WS_HOST, 'echo-protocol', {
    headers: {
      'Origin': EVON_HOST,
      'Cookie': `token=${token}; x-elocs-isrelay=false; x-elocs-token_in_cookie_only=0`,
    }
  });

  const deviceNames = new Map();

  ws.on('open', async () => {
    console.log('✓ Connected!\n');

    // Subscribe to all known security/door/intercom properties
    console.log('=== Subscribing to Security & Intercom Devices ===\n');

    const subscriptions = [
      // Entry door
      {
        Instanceid: 'Door7586',
        Properties: [
          'IsOpen', 'DoorIsOpen', 'CallInProgress', 'DoorOpenTime',
          'DoorBellMelodyTime', 'DoorBellTriggered'
        ]
      },
      // 2N Intercom
      {
        Instanceid: 'Intercom2N1000',
        Properties: [
          'DoorBellTriggered', 'DoorOpenTriggered', 'IsDoorOpen',
          'ConnectionToIntercomHasBeenLost', 'ErrorCode', 'CallInProgress'
        ]
      },
      // Doorbell switch (button)
      {
        Instanceid: 'Intercom2N1000.DoorSwitch',
        Properties: ['IsOn', 'ActValue', 'Error']
      }
    ];

    console.log('Subscribing to:');
    subscriptions.forEach(s => {
      deviceNames.set(s.Instanceid, s.Instanceid);
      console.log(`  ${s.Instanceid}: ${s.Properties.join(', ')}`);
    });
    console.log('');

    send(ws, 'RegisterValuesChanged', [true, subscriptions, true, true]);
  });

  ws.on('message', (data) => {
    try {
      const msg = JSON.parse(data.toString());
      const [type, payload] = msg;
      const time = new Date().toLocaleTimeString();

      // Skip connection message
      if (type === 'Connected') {
        return;
      }

      // Skip user data changes
      if (type === 'Event' && payload?.methodName === 'UserDataChanged') {
        return;
      }

      // Handle GetInstances response
      if (type === 'Callback' && payload?.methodName === 'GetInstances') {
        const className = payload.args?.[0]?.[0]?.ClassName || 'Unknown';
        const result = payload.args?.[0] || [];

        if (result.length > 0) {
          console.log(`✓ Found ${result.length} device(s):`);
          result.forEach(d => {
            console.log(`  ID: ${d.ID}`);
            console.log(`  Name: ${d.Name}`);
            console.log(`  ClassName: ${d.ClassName}`);
            console.log(`  Group: ${d.Group || 'none'}`);

            // Show all properties
            const skipKeys = ['ID', 'Name', 'ClassName', 'Group', 'Authorization'];
            const otherProps = Object.entries(d).filter(([k]) => !skipKeys.includes(k));
            if (otherProps.length > 0) {
              console.log('  Properties:');
              otherProps.forEach(([k, v]) => {
                const val = typeof v === 'object' ? JSON.stringify(v) : v;
                console.log(`    ${k}: ${val}`);
              });
            }

            deviceNames.set(d.ID, d.Name);
            console.log('');

            // Subscribe to ALL properties we can think of
            const propsToWatch = [
              'State', 'IsOpen', 'IsClosed', 'IsLocked', 'IsUnlocked',
              'Open', 'Closed', 'Locked', 'Unlocked', 'Alarm',
              'DoorState', 'LockState', 'Status', 'Active', 'Triggered',
              'Pressed', 'Bell', 'Doorbell', 'Ring', 'Ringing',
              'Contact', 'Input', 'Output', 'Value', 'On', 'IsOn',
              'LastEvent', 'LastChange', 'EventTime', 'Counter',
              'Error', 'Battery', 'Tamper', 'Armed'
            ];

            console.log(`  Subscribing to ${d.ID}...`);
            send(ws, 'RegisterValuesChanged', [true, [{
              Instanceid: d.ID,
              Properties: propsToWatch
            }], true, true]);
          });
        }
        return;
      }

      // Handle GetActionPanelsByAppNames response
      if (type === 'Callback' && payload?.methodName === 'GetActionPanelsByAppNames') {
        const result = payload.args?.[0];
        console.log('GetActionPanelsByAppNames result:');
        console.log(JSON.stringify(result, null, 2));
        console.log('');
        return;
      }

      // Handle GetPropertyValues response
      if (type === 'Callback' && payload?.methodName === 'GetPropertyValues') {
        const result = payload.args?.[0];
        console.log('GetPropertyValues result:');
        if (result && typeof result === 'object') {
          for (const [key, val] of Object.entries(result)) {
            console.log(`  ${key}: ${JSON.stringify(val?.Value ?? val)}`);
          }
        } else {
          console.log(JSON.stringify(result, null, 2));
        }
        console.log('');
        return;
      }

      // Handle GetPropertyNames response
      if (type === 'Callback' && payload?.methodName === 'GetPropertyNames') {
        const result = payload.args?.[0];
        console.log('GetPropertyNames result:');
        console.log(JSON.stringify(result, null, 2));
        console.log('');
        return;
      }

      // Handle GetMethods response
      if (type === 'Callback' && payload?.methodName === 'GetMethods') {
        const result = payload.args?.[0];
        console.log('GetMethods result:');
        console.log(JSON.stringify(result, null, 2));
        console.log('');
        return;
      }

      // Handle ValuesChanged events
      if (type === 'Event' && payload?.methodName === 'ValuesChanged') {
        const table = payload.args?.[0]?.table || {};
        const changes = [];

        for (const [key, entry] of Object.entries(table)) {
          const parts = key.split('.');
          const prop = parts.pop();
          const instanceId = parts.join('.');
          const value = entry.value?.Value;
          const setReason = entry.value?.SetReason;
          const name = deviceNames.get(instanceId) || instanceId;

          changes.push({ instanceId, name, prop, value, setReason });
        }

        if (changes.length > 0) {
          console.log(`[${time}] ════════════════════════════════════════`);
          changes.forEach(({ instanceId, name, prop, value, setReason }) => {
            const reasonTag = setReason && setReason !== 'ValueChanged' ? ` (${setReason})` : '';
            console.log(`  🚪 ${name} (${instanceId})`);
            console.log(`     ${prop} = ${JSON.stringify(value)}${reasonTag}`);
          });
          console.log('');
        }
        return;
      }

      // Handle other callbacks
      if (type === 'Callback') {
        const resolver = pendingCallbacks.get(payload?.sequenceId);
        if (resolver) {
          pendingCallbacks.delete(payload.sequenceId);
          resolver(payload);
        }
        return;
      }

      // Log any other events
      if (type === 'Event') {
        console.log(`[${time}] Event: ${payload?.methodName}`);
        console.log(`  ${JSON.stringify(payload).slice(0, 300)}`);
        console.log('');
        return;
      }

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

  // Start listening message
  setTimeout(() => {
    console.log('');
    console.log('═'.repeat(60));
    console.log('Listening for security door events...');
    console.log('');
    console.log('Try:');
    console.log('  1. Ring the doorbell (DoorBellTriggered)');
    console.log('  2. Open/close the entry door (IsOpen)');
    console.log('  3. Make an intercom call (CallInProgress)');
    console.log('═'.repeat(60));
    console.log('');
  }, 1500);

  // Auto-close after timeout
  setTimeout(() => {
    console.log(`\n⏱️  Timeout after ${TIMEOUT_SECONDS} seconds`);
    ws.close();
  }, TIMEOUT_SECONDS * 1000);

  // Handle Ctrl+C
  process.on('SIGINT', () => {
    console.log('\n\nStopping...');
    ws.close();
  });
}

main().catch(console.error);
