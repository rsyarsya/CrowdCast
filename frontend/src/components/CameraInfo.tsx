import styles from "./CameraInfo.module.css";

interface CameraInfoProps {
  camera_id: string;
  location: string;
  /** ISO 8601 timestamp with timezone offset. */
  timestamp: string;
}

/**
 * CameraInfo shows the camera identity and a human-readable observation time.
 * Pure props-in; no data fetching.
 */
export default function CameraInfo({
  camera_id,
  location,
  timestamp,
}: CameraInfoProps) {
  const readableTimestamp = new Intl.DateTimeFormat("id-ID", {
    dateStyle: "medium",
    timeStyle: "medium",
    timeZone: "Asia/Jakarta",
  }).format(new Date(timestamp));

  return (
    <div className={styles.card}>
      <span className={styles.label}>Identitas Kamera</span>
      <div className={styles.row}>
        <span className={styles.key}>ID Kamera</span>
        <span className={styles.value}>{camera_id}</span>
      </div>
      <div className={styles.row}>
        <span className={styles.key}>Lokasi</span>
        <span className={styles.value}>{location}</span>
      </div>
      <div className={styles.row}>
        <span className={styles.key}>Waktu Pengamatan (WIB)</span>
        <span className={styles.value}>{readableTimestamp}</span>
      </div>
    </div>
  );
}
