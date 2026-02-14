/**
 * Shared authentication logic for Evon Smart Home.
 *
 * Both the HTTP API client and the WebSocket client use this module
 * to perform the login handshake against the Evon controller.
 */

import { API_TIMEOUT_MS } from "./constants.js";

/**
 * Perform a login request against the Evon controller and return the token.
 *
 * @param host  - Base URL of the Evon controller (e.g. "http://192.168.1.x")
 * @param username - The x-elocs-username header value
 * @param password - The x-elocs-password header value (pre-encoded)
 * @returns The authentication token string
 */
export async function performLogin(
  host: string,
  username: string,
  password: string,
): Promise<string> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT_MS);

  try {
    const response = await fetch(`${host}/login`, {
      method: "POST",
      headers: {
        "x-elocs-username": username,
        "x-elocs-password": password,
      },
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`Login failed: ${response.status} ${response.statusText}`);
    }

    const token = response.headers.get("x-elocs-token");
    if (!token) {
      throw new Error("No token received from login");
    }

    return token;
  } catch (error: unknown) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error(`Login timeout after ${API_TIMEOUT_MS}ms`);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}
