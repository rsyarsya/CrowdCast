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
        Kerangka awal antarmuka web untuk pemantauan keramaian berbasis Computer
        Vision dan AI. Integrasi dashboard, autentikasi, dan streaming video akan
        ditambahkan secara bertahap.
      </p>
      <Link href="/dashboard" style={{ color: "var(--purple-400)" }}>
        Buka Dashboard Live Monitoring
      </Link>
    </main>
  );
}
