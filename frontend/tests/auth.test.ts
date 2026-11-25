import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const cookieStore = {
  get: vi.fn(),
  set: vi.fn(),
  delete: vi.fn(),
};

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => cookieStore),
}));

vi.mock("next/navigation", () => ({
  redirect: vi.fn((url: string) => {
    throw new Error(`REDIRECT:${url}`);
  }),
}));

const { loginAction, logoutAction } = await import("@/app/login/actions");
const { getCurrentUser } = await import("@/lib/auth");
const { getLatestMonitoring } = await import("@/lib/monitoring");
const { proxy } = await import("@/proxy");

const TOKEN = {
  access_token: "jwt-token",
  token_type: "bearer",
  expires_in: 28800,
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function form(values: Record<string, string>): FormData {
  const data = new FormData();
  for (const [key, value] of Object.entries(values)) data.set(key, value);
  return data;
}

const NO_ERROR = { error: null };

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_MONITORING_SOURCE", "api");
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
  cookieStore.get.mockReturnValue(undefined);
});

afterEach(() => {
  vi.clearAllMocks();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("loginAction", () => {
  it("stores the token in an httpOnly cookie and redirects to the dashboard", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(TOKEN));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      loginAction(NO_ERROR, form({ email: "op@crowdcast.local", password: "rahasia123" })),
    ).rejects.toThrow("REDIRECT:/dashboard");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://api.test/api/v1/auth/login");
    expect(String(init.body)).toBe("username=op%40crowdcast.local&password=rahasia123");
    expect(cookieStore.set).toHaveBeenCalledWith(
      "crowdcast_token",
      "jwt-token",
      expect.objectContaining({ httpOnly: true, sameSite: "lax", path: "/", maxAge: 28800 }),
    );
  });

  it.each([
    ["/dashboard?camera=CAM-02", "/dashboard?camera=CAM-02"],
    ["//evil.example", "/dashboard"],
    ["https://evil.example", "/dashboard"],
  ])("redirects to next=%s only when it is a local path", async (next, expected) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(TOKEN)));

    await expect(
      loginAction(NO_ERROR, form({ email: "a@b.c", password: "x", next })),
    ).rejects.toThrow(`REDIRECT:${expected}`);
  });

  it("reports wrong credentials without setting a cookie", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ detail: "invalid_credentials" }, 401)),
    );

    const state = await loginAction(NO_ERROR, form({ email: "a@b.c", password: "salah" }));

    expect(state).toEqual({ error: "Email atau password salah." });
    expect(cookieStore.set).not.toHaveBeenCalled();
  });

  it("reports an unreachable backend", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")));

    const state = await loginAction(NO_ERROR, form({ email: "a@b.c", password: "x" }));

    expect(state.error).toContain("Tidak dapat terhubung");
  });

  it("requires both fields before calling the backend", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const state = await loginAction(NO_ERROR, form({ email: "", password: "" }));

    expect(state.error).toBe("Email dan password wajib diisi.");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("session", () => {
  it("logoutAction deletes the cookie and returns to login", async () => {
    await expect(logoutAction()).rejects.toThrow("REDIRECT:/login");
    expect(cookieStore.delete).toHaveBeenCalledWith("crowdcast_token");
  });

  it("monitoring requests carry the session token", async () => {
    cookieStore.get.mockReturnValue({ value: "jwt-token" });
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({}));
    vi.stubGlobal("fetch", fetchMock);

    await getLatestMonitoring("CAM-01");

    expect(fetchMock.mock.calls[0][1].headers).toMatchObject({
      Authorization: "Bearer jwt-token",
    });
  });

  it("maps 401 to the unauthorized code", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ detail: "invalid_token" }, 401)),
    );

    await expect(getLatestMonitoring("CAM-01")).rejects.toMatchObject({
      code: "unauthorized",
    });
  });

  it("getCurrentUser returns null without a cookie and skips the network", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await expect(getCurrentUser()).resolves.toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("proxy", () => {
  it("sends visitors without a session to login and remembers the page", () => {
    const response = proxy(new NextRequest("http://localhost:3000/dashboard"));

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "http://localhost:3000/login?next=%2Fdashboard",
    );
  });

  it("lets requests with a session cookie through", () => {
    const request = new NextRequest("http://localhost:3000/dashboard", {
      headers: { cookie: "crowdcast_token=jwt-token" },
    });

    expect(proxy(request).headers.get("location")).toBeNull();
  });

  it("does not require login in mock mode", () => {
    vi.stubEnv("NEXT_PUBLIC_MONITORING_SOURCE", "mock");

    const response = proxy(new NextRequest("http://localhost:3000/dashboard"));

    expect(response.headers.get("location")).toBeNull();
  });
});
