/**
 * @vitest-environment jsdom
 */
import { describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ApiClient } from "../api/client";
import { setApiInstance } from "../api";
import { agentTaskSnapshotKeys } from "../agents/queries";
import { workspaceKeys } from "../workspace/queries";
import {
  useDeleteRuntime,
  useUnbindAgentsAndDeleteRuntime,
  useUpdateRuntime,
} from "./mutations";
import { runtimeKeys } from "./queries";

const WS_ID = "ws-1";

function setupHooks() {
  const fns = {
    deleteRuntime: vi.fn().mockResolvedValue({}),
    unbindAgentsAndDeleteRuntime: vi.fn().mockResolvedValue({}),
    updateRuntime: vi.fn().mockResolvedValue({}),
  };
  setApiInstance(fns as unknown as ApiClient);
  const queryClient = new QueryClient();
  const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
  const wrapper = ({ children }: { children?: ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);
  return { fns, invalidateSpy, wrapper };
}

describe("runtimes mutations", () => {
  it("useDeleteRuntime deletes the runtime and invalidates the runtime list", async () => {
    const { fns, invalidateSpy, wrapper } = setupHooks();
    const { result } = renderHook(() => useDeleteRuntime(WS_ID), { wrapper });
    await act(async () => {
      await result.current.mutateAsync("rt-1");
    });
    expect(fns.deleteRuntime).toHaveBeenCalledWith("rt-1");
    await waitFor(() =>
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: runtimeKeys.all(WS_ID),
      }),
    );
  });

  it("useUnbindAgentsAndDeleteRuntime deletes and invalidates runtimes, workspace agents and task snapshots", async () => {
    const { fns, invalidateSpy, wrapper } = setupHooks();
    const { result } = renderHook(
      () => useUnbindAgentsAndDeleteRuntime(WS_ID),
      { wrapper },
    );
    await act(async () => {
      await result.current.mutateAsync({
        runtimeId: "rt-1",
        expectedActiveAgentIds: ["a-1", "a-2"],
      });
    });
    expect(fns.unbindAgentsAndDeleteRuntime).toHaveBeenCalledWith("rt-1", [
      "a-1",
      "a-2",
    ]);
    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: runtimeKeys.all(WS_ID),
      });
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: workspaceKeys.agents(WS_ID),
      });
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: agentTaskSnapshotKeys.all(WS_ID),
      });
    });
  });

  it("useUpdateRuntime patches the runtime and invalidates the runtime list", async () => {
    const { fns, invalidateSpy, wrapper } = setupHooks();
    const { result } = renderHook(() => useUpdateRuntime(WS_ID), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({
        runtimeId: "rt-1",
        patch: { visibility: "public" },
      });
    });
    expect(fns.updateRuntime).toHaveBeenCalledWith("rt-1", {
      visibility: "public",
    });
    await waitFor(() =>
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: runtimeKeys.all(WS_ID),
      }),
    );
  });
});
