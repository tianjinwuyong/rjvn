/**
 * @vitest-environment jsdom
 */
import { describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { setApiInstance, type ApiClient } from "../api";
import { workspaceSubscriptionKeys } from "./workspace-subscription-queries";
import {
  useCreateWorkspaceSubscriptionCheckout,
  useCreateWorkspaceSubscriptionPortal,
  usePreviewWorkspaceSeatPurchase,
  usePurchaseWorkspaceSeats,
  useReconcileWorkspaceSubscriptionSeats,
} from "./workspace-subscription-mutations";

const WS_ID = "ws-1";

function setupHooks() {
  const fns = {
    createWorkspaceSubscriptionCheckout: vi
      .fn()
      .mockResolvedValue({ url: "https://checkout.example/session" }),
    reconcileWorkspaceSubscriptionSeats: vi.fn().mockResolvedValue({}),
    previewWorkspaceSeatPurchase: vi.fn().mockResolvedValue({}),
    purchaseWorkspaceSeats: vi.fn().mockResolvedValue({}),
    createWorkspaceSubscriptionPortal: vi
      .fn()
      .mockResolvedValue({ url: "https://portal.example/session" }),
  };
  setApiInstance(fns as unknown as ApiClient);
  const queryClient = new QueryClient();
  const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
  const wrapper = ({ children }: { children?: ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);
  return { fns, invalidateSpy, wrapper };
}

describe("workspace subscription mutations", () => {
  it("useCreateWorkspaceSubscriptionCheckout invalidates the workspace entitlements on success", async () => {
    const { fns, invalidateSpy, wrapper } = setupHooks();
    const { result } = renderHook(
      () => useCreateWorkspaceSubscriptionCheckout(WS_ID),
      { wrapper },
    );
    const request = { plan: "business" } as never;
    await act(async () => {
      await result.current.mutateAsync(request);
    });
    expect(fns.createWorkspaceSubscriptionCheckout).toHaveBeenCalledWith(
      request,
    );
    await waitFor(() =>
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: workspaceSubscriptionKeys.entitlements(WS_ID),
      }),
    );
  });

  it("useReconcileWorkspaceSubscriptionSeats invalidates the workspace entitlements on success", async () => {
    const { fns, invalidateSpy, wrapper } = setupHooks();
    const { result } = renderHook(
      () => useReconcileWorkspaceSubscriptionSeats(WS_ID),
      { wrapper },
    );
    await act(async () => {
      await result.current.mutateAsync();
    });
    expect(fns.reconcileWorkspaceSubscriptionSeats).toHaveBeenCalledTimes(1);
    await waitFor(() =>
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: workspaceSubscriptionKeys.entitlements(WS_ID),
      }),
    );
  });

  it("usePreviewWorkspaceSeatPurchase previews and invalidates nothing", async () => {
    const { fns, invalidateSpy, wrapper } = setupHooks();
    const { result } = renderHook(() => usePreviewWorkspaceSeatPurchase(), {
      wrapper,
    });
    const request = { count: 3 } as never;
    await act(async () => {
      await result.current.mutateAsync(request);
    });
    expect(fns.previewWorkspaceSeatPurchase).toHaveBeenCalledWith(request);
    expect(invalidateSpy).not.toHaveBeenCalled();
  });

  it("usePurchaseWorkspaceSeats invalidates entitlements and summary on success", async () => {
    const { fns, invalidateSpy, wrapper } = setupHooks();
    const { result } = renderHook(() => usePurchaseWorkspaceSeats(WS_ID), {
      wrapper,
    });
    const request = { count: 2 } as never;
    await act(async () => {
      await result.current.mutateAsync(request);
    });
    expect(fns.purchaseWorkspaceSeats).toHaveBeenCalledWith(request);
    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: workspaceSubscriptionKeys.entitlements(WS_ID),
      });
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: workspaceSubscriptionKeys.summary(WS_ID),
      });
    });
  });

  it("useCreateWorkspaceSubscriptionPortal invalidates the workspace entitlements on success", async () => {
    const { fns, invalidateSpy, wrapper } = setupHooks();
    const { result } = renderHook(
      () => useCreateWorkspaceSubscriptionPortal(WS_ID),
      { wrapper },
    );
    await act(async () => {
      await result.current.mutateAsync("idem-123");
    });
    expect(fns.createWorkspaceSubscriptionPortal).toHaveBeenCalledWith(
      "idem-123",
    );
    await waitFor(() =>
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: workspaceSubscriptionKeys.entitlements(WS_ID),
      }),
    );
  });
});
