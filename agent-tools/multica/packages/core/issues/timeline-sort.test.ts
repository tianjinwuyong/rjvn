import { describe, expect, it } from "vitest";
import type { TimelineEntry } from "@multica/core/types";
import { sortTimelineEntriesAsc } from "./timeline-sort";

function entry(id: string, createdAt: string): TimelineEntry {
  return {
    type: "activity",
    id,
    actor_type: "member",
    actor_id: "actor-1",
    created_at: createdAt,
  };
}

describe("sortTimelineEntriesAsc", () => {
  it("sorts an empty array to an empty array", () => {
    expect(sortTimelineEntriesAsc([])).toEqual([]);
  });

  it("returns a single-element array unchanged", () => {
    const e = entry("a", "2026-01-01T00:00:00Z");
    expect(sortTimelineEntriesAsc([e])).toEqual([e]);
  });

  it("sorts ascending by created_at", () => {
    const entries = [
      entry("c", "2026-03-01T00:00:00Z"),
      entry("a", "2026-01-01T00:00:00Z"),
      entry("b", "2026-02-01T00:00:00Z"),
    ];
    expect(sortTimelineEntriesAsc(entries).map((e) => e.id)).toEqual([
      "a",
      "b",
      "c",
    ]);
  });

  it("breaks equal created_at ties by id ascending", () => {
    const entries = [
      entry("b", "2026-01-01T00:00:00Z"),
      entry("a", "2026-01-01T00:00:00Z"),
      entry("c", "2026-01-01T00:00:00Z"),
    ];
    expect(sortTimelineEntriesAsc(entries).map((e) => e.id)).toEqual([
      "a",
      "b",
      "c",
    ]);
  });

  it("leaves an already-sorted array sorted", () => {
    const entries = [
      entry("a", "2026-01-01T00:00:00Z"),
      entry("b", "2026-02-01T00:00:00Z"),
    ];
    expect(sortTimelineEntriesAsc(entries).map((e) => e.id)).toEqual([
      "a",
      "b",
    ]);
  });

  it("re-orders WebSocket / out-of-order arrivals into created_at ASC", () => {
    // Simulates timeline cache entries arriving out of chronological order
    // (mutation onSuccess + WS events), which this helper exists to absorb.
    const entries = [
      entry("third", "2026-01-03T00:00:00Z"),
      entry("first", "2026-01-01T00:00:00Z"),
      entry("second", "2026-01-02T00:00:00Z"),
    ];
    expect(sortTimelineEntriesAsc(entries).map((e) => e.id)).toEqual([
      "first",
      "second",
      "third",
    ]);
  });

  it("keeps equal-timestamp entries stable by id (not original order)", () => {
    const entries = [
      entry("z", "2026-01-01T00:00:00Z"),
      entry("a", "2026-01-01T00:00:00Z"),
      entry("m", "2026-01-01T00:00:00Z"),
    ];
    expect(sortTimelineEntriesAsc(entries).map((e) => e.id)).toEqual([
      "a",
      "m",
      "z",
    ]);
  });

  it("returns the same array reference it was given (in-place sort)", () => {
    const entries = [
      entry("b", "2026-01-02T00:00:00Z"),
      entry("a", "2026-01-01T00:00:00Z"),
    ];
    const out = sortTimelineEntriesAsc(entries);
    expect(out).toBe(entries);
    expect(out.map((e) => e.id)).toEqual(["a", "b"]);
  });
});
