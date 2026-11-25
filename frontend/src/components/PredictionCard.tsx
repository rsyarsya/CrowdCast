import type { Prediction } from "@/lib/monitoring";

import styles from "./PredictionCard.module.css";

interface PredictionCardProps {
  /** Latest prediction per horizon; empty when none is available yet. */
  predictions: Prediction[];
}

/**
 * PredictionCard lists the predicted crowd per horizon (5/15/30 minutes).
 * Values flagged `is_simulation` are not model output, so the card shows a
 * visible "simulasi" label for them. Pure props-in; no data fetching.
 */
export default function PredictionCard({ predictions }: PredictionCardProps) {
  const hasSimulation = predictions.some((p) => p.is_simulation);

  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <span className={styles.label}>Prediksi Keramaian</span>
        {hasSimulation && <span className={styles.badge}>simulasi</span>}
      </div>
      {predictions.length === 0 ? (
        <p className={styles.empty}>Belum ada prediksi.</p>
      ) : (
        <ul className={styles.list}>
          {predictions.map((p) => (
            <li
              key={p.horizon_minutes}
              className={styles.row}
              aria-label={`Prediksi ${p.horizon_minutes} menit: ${p.predicted_count} orang, ${p.predicted_status}`}
            >
              <span className={styles.key}>+{p.horizon_minutes} menit</span>
              <span className={styles.value}>{p.predicted_count}</span>
              <span className={styles.status}>{p.predicted_status}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
