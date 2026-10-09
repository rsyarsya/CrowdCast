import { describe, expect, it } from "vitest";
import {
  getLatestMonitoring,
  getMonitoringSeries,
} from "@/lib/monitoring";

const CROWD_STATUSES = ["Sepi", "Normal", "Ramai"];
const EXPECTED_KEYS = [
  "camera_id",
  "location",
  "timestamp",
  "people_count",
  "crowd_status",
];

describe("monitoring mock accessors", () => {
  it("getLatestMonitoring resolves a record with exactly the 5 attributes", async () => {
    const latest = await getLatestMonitoring();

    expect(Object.keys(latest).sort()).toEqual([...EXPECTED_KEYS].sort());
    expect(Number.isInteger(latest.people_count)).toBe(true);
    expect(latest.people_count).toBeGreaterThanOrEqual(0);
    expect(CROWD_STATUSES).toContain(latest.crowd_status);
  });

  it("getMonitoringSeries returns 3 records sorted ascending by timestamp", async () => {
    const series = await getMonitoringSeries();

    expect(series).toHaveLength(3);

    const timestamps = series.map((record) => record.timestamp);
    const sorted = [...timestamps].sort();
    expect(timestamps).toEqual(sorted);
  });

  it("the latest record is people_count 37 and crowd_status Ramai", async () => {
    const latest = await getLatestMonitoring();

    expect(latest.people_count).toBe(37);
    expect(latest.crowd_status).toBe("Ramai");
  });
});
