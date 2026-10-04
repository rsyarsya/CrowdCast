import { NextResponse } from "next/server";

// Endpoint verifikasi kesehatan frontend, selaras dengan GET /health pada backend.
export function GET() {
  return NextResponse.json({ status: "ok" });
}
