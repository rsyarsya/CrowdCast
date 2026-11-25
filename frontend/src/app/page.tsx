import Link from "next/link";

export default function Home() {
  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: "0.75rem",
        padding: "2rem",
        textAlign: "center",
      }}
    >
      <h1 style={{ fontSize: "2rem" }}>CrowdCast</h1>
      <p style={{ maxWidth: "40rem", color: "var(--purple-200)" }}>
        Antarmuka web untuk pemantauan keramaian berbasis Computer Vision dan AI.
        Masuk dengan akun operator atau administrator untuk membuka dashboard.
      </p>
      <Link href="/dashboard" style={{ color: "var(--purple-400)" }}>
        Masuk ke Dashboard Live Monitoring
      </Link>
    </main>
  );
}
