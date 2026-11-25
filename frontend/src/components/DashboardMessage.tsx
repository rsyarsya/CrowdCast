import type { MonitoringErrorCode } from "@/lib/monitoring";

import styles from "./DashboardMessage.module.css";

interface DashboardMessageProps {
  code: MonitoringErrorCode;
  cameraId: string;
}

const MESSAGES: Record<MonitoringErrorCode, (cameraId: string) => string> = {
  unauthorized: () => "Sesi berakhir. Silakan masuk kembali.",
  camera_not_found: (id) => `Kamera ${id} tidak ditemukan.`,
  no_monitoring_data: (id) => `Belum ada data monitoring untuk kamera ${id}.`,
  no_prediction: (id) => `Belum ada prediksi untuk kamera ${id}.`,
  network_error: () =>
    "Tidak dapat terhubung ke server CrowdCast. Pastikan backend berjalan.",
  unexpected_response: () => "Terjadi kesalahan saat memuat data monitoring.",
};

/**
 * DashboardMessage replaces the dashboard content when monitoring data cannot
 * be shown. Pure props-in; no data fetching.
 */
export default function DashboardMessage({ code, cameraId }: DashboardMessageProps) {
  return (
    <div className={styles.message} role="alert">
      <span className={styles.title}>Data monitoring belum tersedia</span>
      <p className={styles.text}>{MESSAGES[code](cameraId)}</p>
    </div>
  );
}
