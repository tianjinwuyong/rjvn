import { describe, expect, it, vi } from "vitest";
import {
  runtimeKeys,
  runtimeListOptions,
  runtimeUsageByAgentOptions,
  runtimeUsageByHourOptions,
  runtimeUsageOptions,
} from "./queries";
import { setApiInstance, type ApiClient } from "../api";

const fakeApi = {
  getRuntimeUsage: vi.fn(),
  getRuntimeUsageByAgent: vi.fn(),
  getRuntimeUsageByHour: vi.fn(),
  listRuntimes: vi.fn(),
};
setApiInstance(fakeApi as unknown as ApiClient);

describe("runtimeKeys", () => {
  it("keys the runtime list by workspace and owner flag", () => {
    expect(runtimeKeys.all("ws-1")).toEqual(["runtimes", "ws-1"]);
    expect(runtimeKeys.list("ws-1")).toEqual(["runtimes", "ws-1", "list"]);
    expect(runtimeKeys.listMine("ws-1")).toEqual([
      "runtimes",
      "ws-1",
      "list",
      "mine",
    ]);
  });

  it("keys usage reports by runtime id, days and timezone", () => {
    expect(runtimeKeys.usage("rt-1", 7, "UTC")).toEqual([
      "runtimes",
      "usage",
      "rt-1",
      7,
      "UTC",
    ]);
    expect(runtimeKeys.usageByAgent("rt-1", 7, "UTC")).toEqual([
      "runtimes",
      "usage",
      "by-agent",
      "rt-1",
      7,
      "UTC",
    ]);
    expect(runtimeKeys.usageByHour("rt-1", 7, "UTC")).toEqual([
      "runtimes",
      "usage",
      "by-hour",
      "rt-1",
      7,
      "UTC",
    ]);
  });
});

describe("runtimeListOptions", () => {
  it("uses the shared list key when no owner is requested", () => {
    const opts = runtimeListOptions("ws-1");
    expect(opts.queryKey).toEqual(runtimeKeys.list("ws-1"));
  });

  it("uses the list/mine key when owner=me and passes wsSlug through", async () => {
    const opts = runtimeListOptions("ws-1", "me", "acme");
    expect(opts.queryKey).toEqual(runtimeKeys.listMine("ws-1"));
    await opts.queryFn?.();
    expect(fakeApi.listRuntimes).toHaveBeenCalledWith(
      { workspace_id: "ws-1", owner: "me" },
      "acme",
    );
  });
});

describe("runtimeUsageOptions", () => {
  it("wires the query to api.getRuntimeUsage with { days, tz }", async () => {
    const marker = { rows: [{ usage: 1 }] };
    fakeApi.getRuntimeUsage.mockResolvedValue(marker);
    const opts = runtimeUsageOptions("rt-1", 30, "Asia/Shanghai");
    expect(opts.queryKey).toEqual(runtimeKeys.usage("rt-1", 30, "Asia/Shanghai"));
    expect(opts.staleTime).toBe(60 * 1000);
    const result = await opts.queryFn?.();
    expect(result).toBe(marker);
    expect(fakeApi.getRuntimeUsage).toHaveBeenCalledWith("rt-1", {
      days: 30,
      tz: "Asia/Shanghai",
    });
  });
});

describe("runtimeUsageByAgentOptions", () => {
  it("wires the query to api.getRuntimeUsageByAgent with { days, tz }", async () => {
    const marker = { rows: [] };
    fakeApi.getRuntimeUsageByAgent.mockResolvedValue(marker);
    const opts = runtimeUsageByAgentOptions("rt-1", 7, "UTC");
    expect(opts.queryKey).toEqual(runtimeKeys.usageByAgent("rt-1", 7, "UTC"));
    const result = await opts.queryFn?.();
    expect(result).toBe(marker);
    expect(fakeApi.getRuntimeUsageByAgent).toHaveBeenCalledWith("rt-1", {
      days: 7,
      tz: "UTC",
    });
  });
});

describe("runtimeUsageByHourOptions", () => {
  it("wires the query to api.getRuntimeUsageByHour with { days, tz }", async () => {
    const marker = { rows: [] };
    fakeApi.getRuntimeUsageByHour.mockResolvedValue(marker);
    const opts = runtimeUsageByHourOptions("rt-1", 7, "UTC");
    expect(opts.queryKey).toEqual(runtimeKeys.usageByHour("rt-1", 7, "UTC"));
    const result = await opts.queryFn?.();
    expect(result).toBe(marker);
    expect(fakeApi.getRuntimeUsageByHour).toHaveBeenCalledWith("rt-1", {
      days: 7,
      tz: "UTC",
    });
  });
});
