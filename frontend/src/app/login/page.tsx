import LoginForm from "./LoginForm";
import styles from "./page.module.css";

interface LoginPageProps {
  searchParams: Promise<{ next?: string; expired?: string }>;
}

/** Login screen following docs/images/login-lofi.png: email, password, submit. */
export default async function LoginPage({ searchParams }: LoginPageProps) {
  const { next, expired } = await searchParams;
  const notice = expired ? "Sesi berakhir. Silakan masuk kembali." : undefined;

  return (
    <main className={styles.page}>
      <section className={styles.card} aria-labelledby="login-title">
        <h1 id="login-title" className={styles.title}>
          CrowdCast
        </h1>
        <p className={styles.subtitle}>Masuk untuk memantau keramaian.</p>
        <LoginForm next={next} notice={notice} />
      </section>
    </main>
  );
}
