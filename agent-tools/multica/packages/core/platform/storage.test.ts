import { afterEach, describe, expect, it, vi } from "vitest";
import { defaultStorage } from "./storage";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("defaultStorage", () => {
  it("returns null from getItem when there is no window (SSR)", () => {
    vi.stubGlobal("window", undefined);
    expect(defaultStorage.getItem("key")).toBeNull();
  });

  it("setItem and removeItem are no-ops without a window (SSR)", () => {
    vi.stubGlobal("window", undefined);
    expect(() => {
      defaultStorage.setItem("key", "value");
      defaultStorage.removeItem("key");
    }).not.toThrow();
  });

  it("delegates to the global localStorage when window exists", () => {
    const map = new Map<string, string>();
    const localStorage = {
      getItem: vi.fn((k: string) => map.get(k) ?? null),
      setItem: vi.fn((k: string, v: string) => {
        map.set(k, v);
      }),
      removeItem: vi.fn((k: string) => {
        map.delete(k);
      }),
    };
    vi.stubGlobal("window", { localStorage });
    vi.stubGlobal("localStorage", localStorage);

    defaultStorage.setItem("key", "value");
    expect(localStorage.setItem).toHaveBeenCalledWith("key", "value");
    expect(defaultStorage.getItem("key")).toBe("value");

    defaultStorage.removeItem("key");
    expect(localStorage.removeItem).toHaveBeenCalledWith("key");
    expect(defaultStorage.getItem("key")).toBeNull();
  });
});
