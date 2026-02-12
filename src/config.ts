/**
 * Configuration and password encoding for Evon Smart Home MCP Server
 */

import { config } from "dotenv";
import { createHash } from "crypto";

// Load environment variables from .env file
config();

/**
 * Encode password for Evon API.
 * The x-elocs-password is computed as: Base64(SHA512(username + password))
 */
export function encodePassword(username: string, password: string): string {
  const combined = username + password;
  return createHash("sha512").update(combined, "utf8").digest("base64");
}

/**
 * Check if a password looks like it's already encoded.
 * Encoded passwords are Base64-encoded SHA512 hashes (88 chars, ends with ==).
 * Set EVON_PASSWORD_ENCODED=true to force treating the password as pre-encoded.
 */
export function isPasswordEncoded(password: string): boolean {
  return password.length === 88 && password.endsWith("==");
}

// Environment configuration — read lazily so importing this module for
// utility functions (e.g. in tests) doesn't throw when env vars are unset.
export const EVON_HOST = process.env.EVON_HOST || "";
export const EVON_USERNAME = process.env.EVON_USERNAME || "";

const EVON_PASSWORD_RAW = process.env.EVON_PASSWORD || "";
const forceEncoded = process.env.EVON_PASSWORD_ENCODED === "true";
const forceRaw = process.env.EVON_PASSWORD_ENCODED === "false";
export const EVON_PASSWORD =
  forceEncoded ? EVON_PASSWORD_RAW
  : forceRaw ? encodePassword(EVON_USERNAME, EVON_PASSWORD_RAW)
  : isPasswordEncoded(EVON_PASSWORD_RAW) ? EVON_PASSWORD_RAW
  : encodePassword(EVON_USERNAME, EVON_PASSWORD_RAW);

/**
 * Validate that required environment variables are set.
 * Call this before making API requests rather than at import time.
 */
export function validateConfig(): void {
  if (!EVON_HOST) {
    throw new Error(
      "EVON_HOST environment variable is not set. " +
        "Set it to your Evon system URL (e.g., http://192.168.1.x).",
    );
  }
}
