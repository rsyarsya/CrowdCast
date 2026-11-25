import type { Camera, MonitoringRecord, Prediction } from "./types";

/**
 * Mock data for NEXT_PUBLIC_MONITORING_SOURCE=mock (demo without a backend).
 * Mirrors docs/data/monitoring-simulation.json and the backend seed exactly.
 * This is simulated data, not live camera output.
 */
export const MOCK_CAMERAS: Camera[] = [
  {
    camera_id: "CAM-01",
    name: "Kamera Lobi",
    location: "Lobi Gedung A",
    is_active: true,
  },
];

export const MONITORING_SERIES: MonitoringRecord[] = [
  {
    camera_id: "CAM-01",
    location: "Lobi Gedung A",
    timestamp: "2026-09-23T10:00:00+07:00",
    people_count: 0,
    crowd_status: "Sepi",
  },
  {
    camera_id: "CAM-01",
    location: "Lobi Gedung A",
    timestamp: "2026-09-23T10:01:00+07:00",
    people_count: 18,
    crowd_status: "Normal",
  },
  {
    camera_id: "CAM-01",
    location: "Lobi Gedung A",
    timestamp: "2026-09-23T10:02:00+07:00",
    people_count: 37,
    crowd_status: "Ramai",
  },
];

function simulatedPrediction(
  horizon_minutes: number,
  target_time: string,
  predicted_count: number,
  predicted_status: Prediction["predicted_status"],
): Prediction {
  return {
    camera_id: "CAM-01",
    timestamp: "2026-09-23T10:02:00+07:00",
    horizon_minutes,
    target_time,
    predicted_count,
    predicted_status,
    model_name: "simulation",
    is_simulation: true,
  };
}

/** SIMULASI predictions. These values are mock, not produced by an AI model. */
export const MOCK_PREDICTIONS: Prediction[] = [
  simulatedPrediction(5, "2026-09-23T10:07:00+07:00", 40, "Ramai"),
  simulatedPrediction(15, "2026-09-23T10:17:00+07:00", 45, "Ramai"),
  simulatedPrediction(30, "2026-09-23T10:32:00+07:00", 28, "Normal"),
];
