import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  getCameras,
  getLatestMonitoring,
  getMonitoringSeries,
  getPredictions,
  MonitoringApiError,
} from "@/lib/monitoring";

const CROWD_STATUSES = ["Sepi", "Normal", "Ramai"];
const EXPECTED_KEYS = [
  "camera_id",
  "location",
  "timestamp",
  "people_count",
  "crowd_status",
];

const LATEST = {
  camera_id: "CAM-01",
  location: "Lobi Gedung A",
  timestamp: "2026-09-23T10:02:00+07:00",
  people_count: 37,
  crowd_status: "Ramai",
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("monitoring accessors in mock mode", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_MONITORING_SOURCE", "mock");
  });

  it("getLatestMonitoring resolves a record with exactly the 5 attributes", async () => {
    const latest = await getLatestMonitoring();

    expect(Object.keys(latest).sort()).toEqual([...EXPECTED_KEYS].sort());
    expect(Number.isInteger(latest.people_count)).toBe(true);
    expect(latest.people_count).toBeGreaterThanOrEqual(0);
    expect(CROWD_STATUSES).toContain(latest.crowd_status);
    expect(latest.people_count).toBe(37);
  });

  it("getMonitoringSeries returns 3 records sorted ascending by timestamp", async () => {
    const series = await getMonitoringSeries();

    expect(series).toHaveLength(3);
    const timestamps = series.map((record) => record.timestamp);
    expect(timestamps).toEqual([...timestamps].sort());
  });

  it("getPredictions returns simulated predictions for 5, 15, and 30 minutes", async () => {
    const predictions = await getPredictions();

    expect(predictions.map((p) => p.horizon_minutes)).toEqual([5, 15, 30]);
    expect(predictions.every((p) => p.is_simulation)).toBe(true);
  });

  it("does not call the network", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await getCameras();
    await getLatestMonitoring();

    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("monitoring accessors in api mode", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_MONITORING_SOURCE", "api");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test/");
    vi.stubEnv("NEXT_PUBLIC_DEFAULT_CAMERA_ID", "CAM-01");
  });

  it("fetches the latest record of the default camera without caching", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(LATEST));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getLatestMonitoring()).resolves.toEqual(LATEST);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://api.test/api/v1/cameras/CAM-01/monitoring/latest");
    expect(init).toMatchObject({ cache: "no-store" });
  });

  it("passes history query parameters", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([LATEST]));
    vi.stubGlobal("fetch", fetchMock);

    await getMonitoringSeries("CAM-02", {
      start: "2026-09-23T10:00:00+07:00",
      limit: 50,
    });

    const url = new URL(fetchMock.mock.calls[0][0]);
    expect(url.pathname).toBe("/api/v1/cameras/CAM-02/monitoring");
    expect(url.searchParams.get("start")).toBe("2026-09-23T10:00:00+07:00");
    expect(url.searchParams.get("limit")).toBe("50");
  });

  it.each([
    ["camera_not_found", 404],
    ["no_monitoring_data", 404],
    ["no_prediction", 404],
  ] as const)("maps backend detail %s to a typed error", async (code, status) => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ detail: code }, status)),
    );

    const error = await getPredictions().catch((e: unknown) => e);

    expect(error).toBeInstanceOf(MonitoringApiError);
    expect(error).toMatchObject({ code, status });
  });

  it("reports unknown error bodies as unexpected_response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("Internal Server Error", { status: 500 })),
    );

    await expect(getCameras()).rejects.toMatchObject({
      code: "unexpected_response",
      status: 500,
    });
  });

  it("reports an unreachable backend as network_error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")));

    await expect(getLatestMonitoring()).rejects.toMatchObject({
      code: "network_error",
      status: 0,
    });
  });
});
