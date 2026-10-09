import { MOCK_PREDICTION, MONITORING_SERIES } from "./mock";
import type { MonitoringRecord, Prediction } from "./types";

export type { CrowdStatus, MonitoringRecord, Prediction } from "./types";

/*
 * SWAP-POINT: these async accessors currently resolve local mock data. A
 * future real implementation would fetch from
 * `process.env.NEXT_PUBLIC_API_BASE_URL` (already in frontend/.env.example)
 * while keeping these exact signatures stable, so callers do not change.
 */

export async function getLatestMonitoring(): Promise<MonitoringRecord> {
  return MONITORING_SERIES[MONITORING_SERIES.length - 1];
}

export async function getMonitoringSeries(): Promise<MonitoringRecord[]> {
  return MONITORING_SERIES;
}

export async function getPrediction(): Promise<Prediction> {
  return MOCK_PREDICTION;
}
