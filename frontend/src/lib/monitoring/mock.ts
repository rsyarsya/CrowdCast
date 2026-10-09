import type { MonitoringRecord, Prediction } from "./types";

/**
 * Mock monitoring series mirroring docs/data/monitoring-simulation.json
 * exactly. This is simulated data, not live camera output.
 */
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

/**
 * SIMULASI prediction. These values are mock, not produced by an AI model.
 */
export const MOCK_PREDICTION: Prediction = {
  predicted_count: 45,
  predicted_status: "Ramai",
};
