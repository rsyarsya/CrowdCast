export type CrowdStatus = "Sepi" | "Normal" | "Ramai";

export interface MonitoringRecord {
  camera_id: string;
  location: string;
  /** ISO 8601 timestamp with timezone offset. */
  timestamp: string;
  /** Integer >= 0. */
  people_count: number;
  crowd_status: CrowdStatus;
}

/**
 * Prediction values are SIMULASI (mock), not AI output. They stand in for a
 * future prediction service and must be labeled as simulation in the UI.
 */
export interface Prediction {
  predicted_count: number;
  predicted_status: CrowdStatus;
}
