/**
 * @vitest-environment jsdom
 */
import { describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { setApiInstance, type ApiClient } from "../api";
import { billingKeys } from "./queries";
import {
  useCreateCloudBillingCheckoutSession,
  useCreateCloudBillingPortalSession,
  useInvalidateBillingDataAfterCredit,
} from "./mutations";

function setupHooks() {
  const fns = {
    createCloudBillingCheckoutSession: vi
      .fn()
      .mockResolvedValue({ url: "https://checkout.example/session" }),
    createCloudBillingPortalSession: vi
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

describe("billing mutations", () => {
  it("useCreateCloudBillingCheckoutSession calls the API and invalidates the topups list on settle", async () => {
    const { fns, invalidateSpy, wrapper } = setupHooks();
    const { result } = renderHook(
      () => useCreateCloudBillingCheckoutSession(),
      { wrapper },
    );
    const request = { plan: "starter" } as never;
    await act(async () => {
      await result.current.mutateAsync(request);
    });
    expect(fns.createCloudBillingCheckoutSession).toHaveBeenCalledWith(request);
    await waitFor(() =>
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: [...billingKeys.all(), "topups"],
      }),
    );
  });

  it("useCreateCloudBillingPortalSession calls the portal API and invalidates nothing", async () => {
    const { fns, invalidateSpy, wrapper } = setupHooks();
    const { result } = renderHook(() => useCreateCloudBillingPortalSession(), {
      wrapper,
    });
    await act(async () => {
      await result.current.mutateAsync();
    });
    expect(fns.createCloudBillingPortalSession).toHaveBeenCalledTimes(1);
    expect(invalidateSpy).not.toHaveBeenCalled();
  });

  it("useInvalidateBillingDataAfterCredit invalidates balance, transactions, batches and topups", async () => {
    const { invalidateSpy, wrapper } = setupHooks();
    const { result } = renderHook(() => useInvalidateBillingDataAfterCredit(), {
      wrapper,
    });
    await act(async () => {
      result.current();
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: billingKeys.balance(),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: [...billingKeys.all(), "transactions"],
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: [...billingKeys.all(), "batches"],
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: [...billingKeys.all(), "topups"],
    });
  });
});
