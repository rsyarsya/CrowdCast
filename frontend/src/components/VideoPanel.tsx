import styles from "./VideoPanel.module.css";

/**
 * VideoPanel is the dominant element of the Live Monitoring dashboard. It is a
 * pure presentational placeholder (no video stream yet) that reserves a 16:9
 * area. Streaming integration is pending backend work.
 */
export default function VideoPanel() {
  return (
    <div
      className={styles.panel}
      role="img"
      aria-label="pratinjau video monitoring (placeholder)"
    >
      <span className={styles.label}>Pratinjau Video (placeholder)</span>
    </div>
  );
}
