import CameraInfo from "@/components/CameraInfo";
import CrowdStatusCard from "@/components/CrowdStatusCard";
import DashboardShell from "@/components/DashboardShell";
import PeopleCountCard from "@/components/PeopleCountCard";
import PredictionCard from "@/components/PredictionCard";
import VideoPanel from "@/components/VideoPanel";
import { getLatestMonitoring, getPrediction } from "@/lib/monitoring";

import styles from "./page.module.css";

/**
 * Live Monitoring dashboard. This async Server Component is the only place that
 * fetches data; it uses the FEAT-001 mock accessors (not a live backend yet).
 * The presentational components below are pure props-in. Layout follows the
 * visual-direction hierarchy: video dominant, then people count, crowd status,
 * camera identity, and prediction.
 */
export default async function DashboardPage() {
  const [latest, prediction] = await Promise.all([
    getLatestMonitoring(),
    getPrediction(),
  ]);

  return (
    <DashboardShell>
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
          <PredictionCard prediction={prediction} />
        </div>
      </div>
    </DashboardShell>
  );
}
