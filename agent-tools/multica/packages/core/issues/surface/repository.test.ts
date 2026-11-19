import { describe, expect, it, vi } from "vitest";
import { issueSurfaceGanttOptions } from "./repository";
import { projectGanttIssuesOptions } from "../queries";
import type { IssueSurfaceQueryPlan } from "./query-plan";

vi.mock("../queries", () => ({
  projectGanttIssuesOptions: vi.fn(),
}));

const ganttOptions = { queryKey: ["gantt"] } as never;

function makePlan(): IssueSurfaceQueryPlan {
  return {
    scopeKey: "ws:project:p1",
    queryFilter: {},
    createDefaults: {},
  };
}

describe("issueSurfaceGanttOptions", () => {
  it("delegates to projectGanttIssuesOptions with the plan's assignee types", () => {
    vi.mocked(projectGanttIssuesOptions).mockReturnValue(ganttOptions);
    const result = issueSurfaceGanttOptions("ws-1", "p1", {
      ...makePlan(),
      queryFilter: { assignee_types: ["agent", "member"] },
    });
    expect(projectGanttIssuesOptions).toHaveBeenCalledWith(
      "ws-1",
      "p1",
      ["agent", "member"],
    );
    expect(result).toBe(ganttOptions);
  });

  it("passes undefined when the plan carries no assignee-type narrowing", () => {
    vi.mocked(projectGanttIssuesOptions).mockReturnValue(ganttOptions);
    issueSurfaceGanttOptions("ws-1", "p1", makePlan());
    expect(projectGanttIssuesOptions).toHaveBeenCalledWith(
      "ws-1",
      "p1",
      undefined,
    );
  });
});
