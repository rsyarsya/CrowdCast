// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "@/app/dashboard/page";

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("dashboard composition", () => {
  it("renders the mock monitoring values", async () => {
    vi.stubEnv("NEXT_PUBLIC_MONITORING_SOURCE", "mock");

    // DashboardPage is an async Server Component; await it and render the
    // resolved element tree.
    render(await DashboardPage());

    expect(screen.getByText("37")).toBeTruthy();
    // "Ramai" also appears in the prediction card, so assert the crowd status
    // via its unambiguous aria-label.
    expect(screen.getByLabelText("Status keramaian: Ramai")).toBeTruthy();
    expect(screen.getByText("CAM-01")).toBeTruthy();
    expect(screen.getByText("Lobi Gedung A")).toBeTruthy();
    expect(
      screen.getByLabelText("Prediksi 15 menit: 45 orang, Ramai"),
    ).toBeTruthy();
    expect(screen.getByText("simulasi")).toBeTruthy();
  });

  it("shows a message instead of crashing when the backend is unreachable", async () => {
    vi.stubEnv("NEXT_PUBLIC_MONITORING_SOURCE", "api");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")));

    render(await DashboardPage());

    expect(screen.getByRole("alert").textContent).toContain(
      "Tidak dapat terhubung ke server CrowdCast",
    );
  });

  it("keeps monitoring values when there is no prediction yet", async () => {
    vi.stubEnv("NEXT_PUBLIC_MONITORING_SOURCE", "api");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        url.endsWith("/monitoring/latest")
          ? jsonResponse({
              camera_id: "CAM-01",
              location: "Lobi Gedung A",
              timestamp: "2026-09-23T10:02:00+07:00",
              people_count: 12,
              crowd_status: "Normal",
            })
          : jsonResponse({ detail: "no_prediction" }, 404),
      ),
    );

    render(await DashboardPage());

    expect(screen.getByText("12")).toBeTruthy();
    expect(screen.getByText("Belum ada prediksi.")).toBeTruthy();
    expect(screen.queryByText("simulasi")).toBeNull();
  });
});
