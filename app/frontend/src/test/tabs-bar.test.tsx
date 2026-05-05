import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { TabsBar } from "../components/home/tabs-bar";
import { WorkspaceTab } from "../components/home/workspace-types";

const tabs: WorkspaceTab[] = [
  {
    id: "tab-launchpad",
    kind: "launchpad",
    title: "Launchpad",
  },
  {
    id: "tab-report-run-1",
    kind: "report",
    title: "NVDA",
    runId: "run-1",
  },
];

describe("TabsBar", () => {
  it("renders launchpad and report tabs with close button only on report", () => {
    render(
      <TabsBar
        tabs={tabs}
        activeTabId="tab-launchpad"
        onSelect={vi.fn()}
        onClose={vi.fn()}
        onCreateNew={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Launchpad" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "NVDA" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Close NVDA" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New research tab" })).toBeInTheDocument();
  });

  it("calls handlers when selecting tab, closing report tab, and creating new tab", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const onClose = vi.fn();
    const onCreateNew = vi.fn();

    render(
      <TabsBar
        tabs={tabs}
        activeTabId="tab-report-run-1"
        onSelect={onSelect}
        onClose={onClose}
        onCreateNew={onCreateNew}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Launchpad" }));
    await user.click(screen.getByRole("button", { name: "Close NVDA" }));
    await user.click(screen.getByRole("button", { name: "New research tab" }));

    expect(onSelect).toHaveBeenCalledWith("tab-launchpad");
    expect(onClose).toHaveBeenCalledWith("tab-report-run-1");
    expect(onCreateNew).toHaveBeenCalledTimes(1);
  });
});
