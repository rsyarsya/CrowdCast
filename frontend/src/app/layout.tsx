import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CrowdCast",
  description:
    "Antarmuka web CrowdCast untuk pemantauan keramaian berbasis Computer Vision dan AI.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="id">
      <body>{children}</body>
    </html>
  );
}
