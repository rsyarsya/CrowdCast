// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import DashboardPage from "@/app/dashboard/page";

afterEach(() => {
  cleanup();
});

describe("dashboard composition", () => {
  it("renders the mock monitoring values", async () => {
    // DashboardPage is an async Server Component; await it and render the
    // resolved element tree.
    const element = await DashboardPage();
    render(element);

    expect(screen.getByText("37")).toBeTruthy();
    // "Ramai" also appears in the prediction card, so assert the crowd status
    // via its unambiguous aria-label.
    expect(screen.getByLabelText("Status keramaian: Ramai")).toBeTruthy();
    expect(screen.getByText("CAM-01")).toBeTruthy();
    expect(screen.getByText("Lobi Gedung A")).toBeTruthy();
  });
});
