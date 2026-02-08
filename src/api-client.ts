/**
 * API client for Evon Smart Home
 */

import { EVON_HOST, EVON_USERNAME, EVON_PASSWORD } from "./config.js";
import { API_TIMEOUT_MS, TOKEN_VALIDITY_DAYS } from "./constants.js";
import type { ApiResponse } from "./types.js";

let currentToken: string | null = null;
let tokenExpiry: number = 0;

export async function login(): Promise<string> {
  if (currentToken && Date.now() < tokenExpiry - 60000) {
    return currentToken;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT_MS);

  try {
  const response = await fetch(`${EVON_HOST}/login`, {
    method: "POST",
    headers: {
      "x-elocs-username": EVON_USERNAME,
      "x-elocs-password": EVON_PASSWORD,
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

  currentToken = token;
  tokenExpiry = Date.now() + TOKEN_VALIDITY_DAYS * 24 * 60 * 60 * 1000;

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

export async function apiRequest<T>(
  endpoint: string,
  method: "GET" | "POST" | "PUT" = "GET",
  body?: unknown
): Promise<ApiResponse<T>> {
  const token = await login();

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT_MS);

  try {
    const fetchOptions: RequestInit = {
      method,
      headers: {
        Cookie: `token=${token}`,
        "Content-Type": "application/json",
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    };

    let response = await fetch(`${EVON_HOST}/api${endpoint}`, fetchOptions);

    // Handle token expiry with retry using a fresh timeout
    if (response.status === 302 || response.status === 401) {
      clearTimeout(timeoutId);
      currentToken = null;
      const newToken = await login();
      const retryController = new AbortController();
      const retryTimeoutId = setTimeout(() => retryController.abort(), API_TIMEOUT_MS);
      try {
        response = await fetch(`${EVON_HOST}/api${endpoint}`, {
          method,
          headers: {
            Cookie: `token=${newToken}`,
            "Content-Type": "application/json",
          },
          body: body !== undefined ? JSON.stringify(body) : undefined,
          signal: retryController.signal,
        });
      } finally {
        clearTimeout(retryTimeoutId);
      }
    }

    if (!response.ok) {
      throw new Error(`API request failed: ${response.status}`);
    }

    return await response.json();
  } catch (error: unknown) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error(`API request timeout after ${API_TIMEOUT_MS}ms: ${endpoint}`);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function callMethod(
  instanceId: string,
  methodName: string,
  params: unknown[] = []
): Promise<ApiResponse<unknown>> {
  return apiRequest(`/instances/${instanceId}/${methodName}`, "POST", params);
}
