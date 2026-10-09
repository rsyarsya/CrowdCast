import type { Prediction } from "@/lib/monitoring";

import styles from "./PredictionCard.module.css";

interface PredictionCardProps {
  prediction: Prediction;
}

/**
 * PredictionCard renders the predicted crowd figures. Values are SIMULASI
 * (mock), not AI output, and the card shows a visible "simulasi" label to make
 * that explicit. Pure props-in; no data fetching.
 */
export default function PredictionCard({ prediction }: PredictionCardProps) {
  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <span className={styles.label}>Prediksi Keramaian</span>
        <span className={styles.badge}>simulasi</span>
      </div>
      <div className={styles.row}>
        <span className={styles.key}>Perkiraan Jumlah Orang</span>
        <span className={styles.value}>{prediction.predicted_count}</span>
      </div>
      <div className={styles.row}>
        <span className={styles.key}>Perkiraan Status</span>
        <span className={styles.value}>{prediction.predicted_status}</span>
      </div>
    </div>
  );
}
