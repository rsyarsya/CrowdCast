import type { CSSProperties } from "react";

import type { CrowdStatus } from "@/lib/monitoring";

import styles from "./CrowdStatusCard.module.css";

interface CrowdStatusCardProps {
  crowd_status: CrowdStatus;
}

/*
 * TEMPORARY ASSUMPTION pending team decision (palette doc marks the status
 * color mapping as TBD): each crowd status maps to a status CSS variable
 * defined in globals.css.
 */
const STATUS_COLOR_VAR: Record<CrowdStatus, string> = {
  Sepi: "var(--status-sepi)",
  Normal: "var(--status-normal)",
  Ramai: "var(--status-ramai)",
};

/**
 * CrowdStatusCard renders the crowd status text colored by a documented map.
 * Pure props-in; no data fetching.
 */
export default function CrowdStatusCard({ crowd_status }: CrowdStatusCardProps) {
  const statusStyle: CSSProperties = { color: STATUS_COLOR_VAR[crowd_status] };

  return (
    <div className={styles.card}>
      <span className={styles.label}>Status Keramaian</span>
      <span
        className={styles.status}
        style={statusStyle}
        aria-label={`Status keramaian: ${crowd_status}`}
      >
        {crowd_status}
      </span>
    </div>
  );
}
