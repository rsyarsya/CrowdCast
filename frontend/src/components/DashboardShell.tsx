import Link from "next/link";
import type { ReactNode } from "react";

import { logoutAction } from "@/app/login/actions";
import type { CurrentUser } from "@/lib/auth";

import styles from "./DashboardShell.module.css";

interface DashboardShellProps {
  children: ReactNode;
  /** Logged-in user; omitted in mock mode or when it could not be loaded. */
  user?: Pick<CurrentUser, "name" | "role"> | null;
}

const ROLE_LABEL: Record<CurrentUser["role"], string> = {
  operator: "Operator",
  admin: "Administrator",
};

/**
 * DashboardShell provides the header (title, nav, and session) and renders
 * children below it. Pure props-in; no data fetching. History stays
 * unavailable until its route is implemented.
 */
export default function DashboardShell({ children, user }: DashboardShellProps) {
  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <span className={styles.title}>CrowdCast</span>
        <nav className={styles.nav} aria-label="Navigasi utama">
          <Link className={styles.link} href="/dashboard">
            Dashboard
          </Link>
          <span className={styles.unavailable} aria-disabled="true">
            History (Segera hadir)
          </span>
        </nav>
        {user && (
          <div className={styles.session}>
            <span className={styles.user}>
              {user.name} · {ROLE_LABEL[user.role]}
            </span>
            <form action={logoutAction}>
              <button className={styles.logout} type="submit">
                Keluar
              </button>
            </form>
          </div>
        )}
      </header>
      <main className={styles.content}>{children}</main>
    </div>
  );
}
