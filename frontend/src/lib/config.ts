/**
 * Shared frontend configuration. Values are read on every call so tests can
 * override the environment.
 */

/** httpOnly cookie that holds the backend access token. */
export const TOKEN_COOKIE = "crowdcast_token";

export function apiBaseUrl(): string {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  return base.replace(/\/+$/, "");
}

/** Mock mode serves local simulation data and skips login. */
export function isMockSource(): boolean {
  return process.env.NEXT_PUBLIC_MONITORING_SOURCE === "mock";
}
