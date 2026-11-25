// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import CameraInfo from "@/components/CameraInfo";
import CrowdStatusCard from "@/components/CrowdStatusCard";
import PeopleCountCard from "@/components/PeopleCountCard";
import DashboardMessage from "@/components/DashboardMessage";
import PredictionCard from "@/components/PredictionCard";
import VideoPanel from "@/components/VideoPanel";
import { MOCK_PREDICTIONS } from "@/lib/monitoring/mock";

afterEach(() => {
  cleanup();
});

describe("presentational components", () => {
  it("VideoPanel exposes the placeholder aria-label", () => {
    render(<VideoPanel />);

    expect(
      screen.getByLabelText("pratinjau video monitoring (placeholder)"),
    ).toBeTruthy();
  });

  it("PeopleCountCard shows the passed count", () => {
    render(<PeopleCountCard people_count={37} />);

    expect(screen.getByText("37")).toBeTruthy();
  });

  it("CrowdStatusCard renders the status text and its aria-label", () => {
    render(<CrowdStatusCard crowd_status="Ramai" />);

    expect(screen.getByText("Ramai")).toBeTruthy();
    expect(screen.getByLabelText("Status keramaian: Ramai")).toBeTruthy();
  });

  it("CameraInfo shows camera_id and location", () => {
    render(
      <CameraInfo
        camera_id="CAM-01"
        location="Lobi Gedung A"
        timestamp="2026-09-23T10:02:00+07:00"
      />,
    );

    expect(screen.getByText("CAM-01")).toBeTruthy();
    expect(screen.getByText("Lobi Gedung A")).toBeTruthy();
  });

  it("PredictionCard lists every horizon and labels simulated values", () => {
    render(<PredictionCard predictions={MOCK_PREDICTIONS} />);

    expect(screen.getByText("simulasi")).toBeTruthy();
    expect(screen.getByText("+5 menit")).toBeTruthy();
    expect(screen.getByText("+15 menit")).toBeTruthy();
    expect(screen.getByText("+30 menit")).toBeTruthy();
  });

  it("PredictionCard hides the simulasi label for model predictions", () => {
    const predictions = MOCK_PREDICTIONS.map((p) => ({
      ...p,
      model_name: "moving_average",
      is_simulation: false,
    }));
    render(<PredictionCard predictions={predictions} />);

    expect(screen.queryByText("simulasi")).toBeNull();
  });

  it("PredictionCard shows an empty state without predictions", () => {
    render(<PredictionCard predictions={[]} />);

    expect(screen.getByText("Belum ada prediksi.")).toBeTruthy();
  });

  it("DashboardMessage explains a missing camera", () => {
    render(<DashboardMessage code="camera_not_found" cameraId="CAM-09" />);

    expect(screen.getByRole("alert").textContent).toContain(
      "Kamera CAM-09 tidak ditemukan.",
    );
  });
});
