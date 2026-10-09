import Link from "next/link";
import type { ReactNode } from "react";

import styles from "./DashboardShell.module.css";

interface DashboardShellProps {
  children: ReactNode;
}

/**
 * DashboardShell provides the header (title + nav) and renders children below
 * it. Pure props-in; no data fetching. The History link is a placeholder for a
 * future route.
 */
export default function DashboardShell({ children }: DashboardShellProps) {
  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <span className={styles.title}>CrowdCast</span>
        <nav className={styles.nav} aria-label="Navigasi utama">
          <Link className={styles.link} href="/dashboard">
            Dashboard
          </Link>
          {/* History route is a placeholder; the page does not exist yet. */}
          <Link className={styles.link} href="/history">
            History
          </Link>
        </nav>
      </header>
      <main className={styles.content}>{children}</main>
    </div>
  );
}
