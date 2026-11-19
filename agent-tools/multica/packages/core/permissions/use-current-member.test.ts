/**
 * @vitest-environment jsdom
 */
import { describe, expect, it, vi, type Mock } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { setApiInstance, type ApiClient } from "../api";
import type { MemberRole, MemberWithUser } from "../types";
import { memberListOptions } from "../workspace/queries";
import { useAuthStore } from "../auth";
import { useCurrentMember } from "./use-current-member";

vi.mock("../auth", () => ({
  useAuthStore: vi.fn(),
}));

const WS_ID = "ws-1";
const USER_ID = "u-1";

function makeMember(role: MemberRole): MemberWithUser {
  return {
    id: `member-${role}`,
    workspace_id: WS_ID,
    user_id: USER_ID,
    role,
    created_at: "2026-01-01T00:00:00Z",
    name: USER_ID,
    email: `${USER_ID}@example.com`,
    avatar_url: null,
  };
}

function setup(members: MemberWithUser[], userId: string | null) {
  const listMembers = vi.fn().mockResolvedValue(members);
  setApiInstance({ listMembers } as unknown as ApiClient);
  const queryClient = new QueryClient();
  queryClient.setQueryData(memberListOptions(WS_ID).queryKey, members);
  (useAuthStore as unknown as Mock).mockReturnValue({
    user: userId === null ? null : { id: userId },
  });
  const wrapper = ({ children }: { children?: ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);
  return wrapper;
}

describe("useCurrentMember", () => {
  it("resolves the current user's member record and role", async () => {
    const member = makeMember("admin");
    const { result } = renderHook(() => useCurrentMember(WS_ID), {
      wrapper: setup([member], USER_ID),
    });
    await act(async () => {
      await Promise.resolve();
    });
    expect(result.current).toEqual({
      userId: USER_ID,
      role: "admin",
      member,
      isLoading: false,
    });
  });

  it("returns a null member and role when the user is not in the workspace", async () => {
    const { result } = renderHook(() => useCurrentMember(WS_ID), {
      wrapper: setup([makeMember("member")], "u-2"),
    });
    await act(async () => {
      await Promise.resolve();
    });
    expect(result.current.userId).toBe("u-2");
    expect(result.current.member).toBeNull();
    expect(result.current.role).toBeNull();
    expect(result.current.isLoading).toBe(false);
  });

  it("returns nulls when logged out", async () => {
    const { result } = renderHook(() => useCurrentMember(WS_ID), {
      wrapper: setup([makeMember("member")], null),
    });
    await act(async () => {
      await Promise.resolve();
    });
    expect(result.current.userId).toBeNull();
    expect(result.current.member).toBeNull();
    expect(result.current.role).toBeNull();
    expect(result.current.isLoading).toBe(false);
  });
});
