// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import CameraInfo from "@/components/CameraInfo";
import CrowdStatusCard from "@/components/CrowdStatusCard";
import PeopleCountCard from "@/components/PeopleCountCard";
import PredictionCard from "@/components/PredictionCard";
import VideoPanel from "@/components/VideoPanel";

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

  it("PredictionCard shows the simulasi label", () => {
    render(
      <PredictionCard
        prediction={{ predicted_count: 45, predicted_status: "Ramai" }}
      />,
    );

    expect(screen.getByText("simulasi")).toBeTruthy();
  });
});
