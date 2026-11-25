"use client";

import DashboardShell from "@/components/DashboardShell";

import styles from "./page.module.css";

/**
 * Route error boundary for unexpected dashboard failures. Known API errors
 * (backend down, unknown camera, no data) are rendered by the page itself.
 */
export default function DashboardError({ reset }: { error: Error; reset: () => void }) {
  return (
    <DashboardShell>
      <div className={styles.error} role="alert">
        <p>Terjadi kesalahan saat menampilkan dashboard.</p>
        <button type="button" className={styles.retry} onClick={reset}>
          Coba lagi
        </button>
      </div>
    </DashboardShell>
  );
}
