export type CrowdStatus = "Sepi" | "Normal" | "Ramai";

/** GET /api/v1/cameras item. The video source is never exposed. */
export interface Camera {
  camera_id: string;
  name: string;
  location: string;
  is_active: boolean;
}

export interface MonitoringRecord {
  camera_id: string;
  location: string;
  /** ISO 8601 timestamp with timezone offset (WIB, +07:00). */
  timestamp: string;
  /** Integer >= 0. */
  people_count: number;
  crowd_status: CrowdStatus;
}

/**
 * Latest prediction for one horizon. `is_simulation` is true for mock/seeded
 * values that are not produced by a forecasting model; the UI must label them.
 */
export interface Prediction {
  camera_id: string;
  /** When the prediction was made (ISO 8601, WIB). */
  timestamp: string;
  /** Minutes ahead: 5, 15, or 30. */
  horizon_minutes: number;
  /** timestamp + horizon_minutes (ISO 8601, WIB). */
  target_time: string;
  predicted_count: number;
  predicted_status: CrowdStatus;
  model_name: string;
  is_simulation: boolean;
}

/**
 * Stable error codes from the backend `detail`, plus client-side codes for
 * network failures and unexpected responses.
 */
export type MonitoringErrorCode =
  | "unauthorized"
  | "camera_not_found"
  | "no_monitoring_data"
  | "no_prediction"
  | "network_error"
  | "unexpected_response";
