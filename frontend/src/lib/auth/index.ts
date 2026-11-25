import { apiBaseUrl } from "@/lib/config";

import { getAccessToken } from "./session";

export type UserRole = "operator" | "admin";

/** GET /api/v1/auth/me */
export interface CurrentUser {
  id: number;
  email: string;
  name: string;
  role: UserRole;
  is_active: boolean;
}

/** POST /api/v1/auth/login */
export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  /** Seconds until the token expires. */
  expires_in: number;
}

export type LoginResult =
  | { ok: true; token: LoginResponse }
  | { ok: false; error: "invalid_credentials" | "network_error" | "unexpected_response" };

/** Exchange email and password for a token. Never throws. */
export async function requestLogin(email: string, password: string): Promise<LoginResult> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}/api/v1/auth/login`, {
      method: "POST",
      cache: "no-store",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ username: email, password }),
    });
  } catch {
    return { ok: false, error: "network_error" };
  }
  if (response.status === 401 || response.status === 422) {
    return { ok: false, error: "invalid_credentials" };
  }
  if (!response.ok) return { ok: false, error: "unexpected_response" };
  return { ok: true, token: (await response.json()) as LoginResponse };
}

/** The logged-in user, or null when there is no valid session. */
export async function getCurrentUser(): Promise<CurrentUser | null> {
  const token = await getAccessToken();
  if (!token) return null;
  try {
    const response = await fetch(`${apiBaseUrl()}/api/v1/auth/me`, {
      cache: "no-store",
      headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
    });
    return response.ok ? ((await response.json()) as CurrentUser) : null;
  } catch {
    return null;
  }
}
