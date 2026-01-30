/**
 * Configuration and password encoding for Evon Smart Home MCP Server
 */

import { createHash } from "crypto";

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
 */
export function isPasswordEncoded(password: string): boolean {
  return password.length === 88 && password.endsWith("==");
}

// Environment configuration
export const EVON_HOST = process.env.EVON_HOST || "http://192.168.1.4";
export const EVON_USERNAME = process.env.EVON_USERNAME || "";

const EVON_PASSWORD_RAW = process.env.EVON_PASSWORD || "";
export const EVON_PASSWORD = isPasswordEncoded(EVON_PASSWORD_RAW)
  ? EVON_PASSWORD_RAW
  : encodePassword(EVON_USERNAME, EVON_PASSWORD_RAW);
