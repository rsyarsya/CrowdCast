import { MOCK_CAMERAS, MOCK_PREDICTIONS, MONITORING_SERIES } from "./mock";
import type {
  Camera,
  MonitoringErrorCode,
  MonitoringRecord,
  Prediction,
} from "./types";

export type {
  Camera,
  CrowdStatus,
  MonitoringErrorCode,
  MonitoringRecord,
  Prediction,
} from "./types";

/**
 * Data accessors for the monitoring UI. They call the CrowdCast backend
 * (`/api/v1`) unless NEXT_PUBLIC_MONITORING_SOURCE=mock, which serves the
 * local mock data for demos without a backend.
 *
 * Environment (read on every call so tests can override it):
 * - NEXT_PUBLIC_API_BASE_URL: backend origin, default http://localhost:8000
 * - NEXT_PUBLIC_DEFAULT_CAMERA_ID: camera shown by default, default CAM-01
 * - NEXT_PUBLIC_MONITORING_SOURCE: "api" (default) or "mock"
 */

const KNOWN_ERROR_CODES: readonly MonitoringErrorCode[] = [
  "camera_not_found",
  "no_monitoring_data",
  "no_prediction",
];

export class MonitoringApiError extends Error {
  constructor(
    readonly code: MonitoringErrorCode,
    readonly status: number,
  ) {
    super(`Monitoring API error: ${code} (HTTP ${status})`);
    this.name = "MonitoringApiError";
  }
}

function isMockSource(): boolean {
  return process.env.NEXT_PUBLIC_MONITORING_SOURCE === "mock";
}

function apiBaseUrl(): string {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  return base.replace(/\/+$/, "");
}

export function defaultCameraId(): string {
  return process.env.NEXT_PUBLIC_DEFAULT_CAMERA_ID || "CAM-01";
}

async function request<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}/api/v1${path}`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
  } catch {
    throw new MonitoringApiError("network_error", 0);
  }

  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const detail =
      body !== null && typeof body === "object" && "detail" in body
        ? (body as { detail: unknown }).detail
        : null;
    const code = KNOWN_ERROR_CODES.find((known) => known === detail);
    throw new MonitoringApiError(code ?? "unexpected_response", response.status);
  }
  return (await response.json()) as T;
}

function cameraPath(cameraId: string): string {
  return `/cameras/${encodeURIComponent(cameraId)}`;
}

export async function getCameras(): Promise<Camera[]> {
  if (isMockSource()) return MOCK_CAMERAS;
  return request<Camera[]>("/cameras");
}

export async function getLatestMonitoring(
  cameraId: string = defaultCameraId(),
): Promise<MonitoringRecord> {
  if (isMockSource()) return MONITORING_SERIES[MONITORING_SERIES.length - 1];
  return request<MonitoringRecord>(`${cameraPath(cameraId)}/monitoring/latest`);
}

export interface SeriesQuery {
  /** ISO 8601 with offset, inclusive. */
  start?: string;
  /** ISO 8601 with offset, inclusive. */
  end?: string;
  /** 1..2000, backend default 500. */
  limit?: number;
}

/** History in ascending time order (latest window when `start` is omitted). */
export async function getMonitoringSeries(
  cameraId: string = defaultCameraId(),
  query: SeriesQuery = {},
): Promise<MonitoringRecord[]> {
  if (isMockSource()) return MONITORING_SERIES;
  const params = new URLSearchParams();
  if (query.start) params.set("start", query.start);
  if (query.end) params.set("end", query.end);
  if (query.limit !== undefined) params.set("limit", String(query.limit));
  const search = params.size > 0 ? `?${params}` : "";
  return request<MonitoringRecord[]>(
    `${cameraPath(cameraId)}/monitoring${search}`,
  );
}

/** Latest prediction per horizon, ordered 5, 15, 30 minutes. */
export async function getPredictions(
  cameraId: string = defaultCameraId(),
): Promise<Prediction[]> {
  if (isMockSource()) return MOCK_PREDICTIONS;
  return request<Prediction[]>(`${cameraPath(cameraId)}/predictions/latest`);
}
