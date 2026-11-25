"use client";

import { useActionState } from "react";

import { loginAction, type LoginState } from "./actions";
import styles from "./page.module.css";

const INITIAL_STATE: LoginState = { error: null };

interface LoginFormProps {
  next?: string;
  notice?: string;
}

export default function LoginForm({ next, notice }: LoginFormProps) {
  const [state, formAction, pending] = useActionState(loginAction, INITIAL_STATE);
  const message = state.error ?? notice;

  return (
    <form className={styles.form} action={formAction}>
      {next && <input type="hidden" name="next" value={next} />}
      <label className={styles.field}>
        <span>Email</span>
        <input name="email" type="email" autoComplete="username" required />
      </label>
      <label className={styles.field}>
        <span>Password</span>
        <input name="password" type="password" autoComplete="current-password" required />
      </label>
      {message && (
        <p className={styles.message} role="alert">
          {message}
        </p>
      )}
      <button className={styles.submit} type="submit" disabled={pending}>
        {pending ? "Memproses..." : "Masuk"}
      </button>
    </form>
  );
}
