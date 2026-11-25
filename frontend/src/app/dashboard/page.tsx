import { redirect } from "next/navigation";

import CameraInfo from "@/components/CameraInfo";
import CrowdStatusCard from "@/components/CrowdStatusCard";
import DashboardMessage from "@/components/DashboardMessage";
import DashboardShell from "@/components/DashboardShell";
import PeopleCountCard from "@/components/PeopleCountCard";
import PredictionCard from "@/components/PredictionCard";
import VideoPanel from "@/components/VideoPanel";
import { getCurrentUser } from "@/lib/auth";
import {
  defaultCameraId,
  getLatestMonitoring,
  getPredictions,
  MonitoringApiError,
} from "@/lib/monitoring";

import styles from "./page.module.css";

// Monitoring data changes constantly: render on every request, never at build.
export const dynamic = "force-dynamic";

/**
 * Live Monitoring dashboard. This async Server Component is the only place that
 * fetches data, through the `@/lib/monitoring` accessors (backend API, or mock
 * data when NEXT_PUBLIC_MONITORING_SOURCE=mock). The presentational components
 * below are pure props-in. Layout follows the visual-direction hierarchy: video
 * dominant, then people count, crowd status, camera identity, and prediction.
 */
function settle<T>(promise: Promise<T>): Promise<PromiseSettledResult<T>> {
  return promise.then(
    (value) => ({ status: "fulfilled", value }),
    (reason: unknown) => ({ status: "rejected", reason }),
  );
}

export default async function DashboardPage() {
  const cameraId = defaultCameraId();
  const [latestResult, predictionsResult, user] = await Promise.all([
    settle(getLatestMonitoring(cameraId)),
    settle(getPredictions(cameraId)),
    getCurrentUser(), // never throws; null in mock mode or without a session
  ]);

  if (latestResult.status === "rejected") {
    const error: unknown = latestResult.reason;
    // Unknown failures go to the route error boundary (error.tsx).
    if (!(error instanceof MonitoringApiError)) throw error;
    // Expired or revoked token: the proxy only checks that a cookie exists.
    if (error.code === "unauthorized") redirect("/login?expired=1");
    return (
      <DashboardShell user={user}>
        <DashboardMessage code={error.code} cameraId={cameraId} />
      </DashboardShell>
    );
  }

  const latest = latestResult.value;
  // Missing predictions should not hide the live monitoring values.
  const predictions =
    predictionsResult.status === "fulfilled" ? predictionsResult.value : [];

  return (
    <DashboardShell user={user}>
      <div className={styles.layout}>
        <div className={styles.video}>
          <VideoPanel />
        </div>
        <div className={styles.grid}>
          <PeopleCountCard people_count={latest.people_count} />
          <CrowdStatusCard crowd_status={latest.crowd_status} />
          <CameraInfo
            camera_id={latest.camera_id}
            location={latest.location}
            timestamp={latest.timestamp}
          />
          <PredictionCard predictions={predictions} />
        </div>
      </div>
    </DashboardShell>
  );
}
