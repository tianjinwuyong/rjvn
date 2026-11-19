/**
 * @vitest-environment jsdom
 */
import { describe, expect, it, vi, type Mock } from "vitest";
import { renderHook } from "@testing-library/react";
import type { Agent, MemberRole, Skill } from "../types";
import { useCurrentMember } from "./use-current-member";
import {
  useAgentPermissions,
  useSkillPermissions,
} from "./use-resource-permissions";
import { deny } from "./types";

vi.mock("./use-current-member", () => ({
  useCurrentMember: vi.fn(),
}));

const WS_ID = "ws-1";
const USER_ID = "u-1";

const mockUseCurrentMember = useCurrentMember as unknown as Mock;

function mountAgent(agent: Agent | null, role: MemberRole | null) {
  mockUseCurrentMember.mockReturnValue({
    userId: USER_ID,
    role,
    member: null,
    isLoading: false,
  });
  return renderHook(() => useAgentPermissions(agent, WS_ID)).result.current;
}

function mountSkill(skill: Skill | null, role: MemberRole | null) {
  mockUseCurrentMember.mockReturnValue({
    userId: USER_ID,
    role,
    member: null,
    isLoading: false,
  });
  return renderHook(() => useSkillPermissions(skill, WS_ID)).result.current;
}

function makeAgent(overrides: Record<string, unknown>): Agent {
  return {
    owner_id: USER_ID,
    permission_mode: "public_to",
    invocation_targets: [{ target_type: "workspace", target_id: WS_ID }],
    ...overrides,
  } as unknown as Agent;
}

function makeSkill(overrides: Record<string, unknown>): Skill {
  return { created_by: "u-2", ...overrides } as unknown as Skill;
}

describe("useAgentPermissions", () => {
  it("denies every decision while the resource is null", () => {
    const out = mountAgent(null, "admin");
    expect(out).toEqual({
      canEdit: deny("unknown", ""),
      canAssign: deny("unknown", ""),
      isLoading: false,
    });
  });

  it("allows editing for workspace admins", () => {
    const out = mountAgent(makeAgent({ owner_id: null }), "admin");
    expect(out.canEdit.allowed).toBe(true);
    expect(out.canEdit.reason).toBe("allowed");
  });

  it("denies editing for non-owners and non-admins", () => {
    const out = mountAgent(makeAgent({ owner_id: null }), "member");
    expect(out.canEdit.allowed).toBe(false);
    expect(out.canEdit.reason).toBe("not_resource_owner");
  });

  it("allows editing for the agent owner even without an admin role", () => {
    const out = mountAgent(makeAgent({}), "member");
    expect(out.canEdit.allowed).toBe(true);
  });

  it("denies assigning private agents to non-owners (even admins)", () => {
    const out = mountAgent(
      makeAgent({ owner_id: null, permission_mode: "private" }),
      "admin",
    );
    expect(out.canAssign.allowed).toBe(false);
    expect(out.canAssign.reason).toBe("private_visibility");
  });

  it("allows assigning a public_to agent with a workspace grant to any member", () => {
    const out = mountAgent(makeAgent({ owner_id: null }), "member");
    expect(out.canAssign.allowed).toBe(true);
  });

  it("allows assigning a public_to agent with a matching member grant", () => {
    const out = mountAgent(
      makeAgent({
        owner_id: null,
        invocation_targets: [{ target_type: "member", target_id: USER_ID }],
      }),
      "member",
    );
    expect(out.canAssign.allowed).toBe(true);
  });

  it("denies assigning for logged-out users", () => {
    const out = mountAgent(makeAgent({}), null);
    expect(out.canEdit.allowed).toBe(false);
    expect(out.canEdit.reason).toBe("not_authenticated");
  });
});

describe("useSkillPermissions", () => {
  it("denies every decision while the resource is null", () => {
    const out = mountSkill(null, "admin");
    expect(out).toEqual({
      canEdit: deny("unknown", ""),
      canDelete: deny("unknown", ""),
    });
  });

  it("allows editing for workspace admins", () => {
    const out = mountSkill(makeSkill({ created_by: "u-2" }), "admin");
    expect(out.canEdit.allowed).toBe(true);
    expect(out.canDelete.allowed).toBe(true);
  });

  it("allows editing for the creator", () => {
    const out = mountSkill(makeSkill({ created_by: USER_ID }), "member");
    expect(out.canEdit.allowed).toBe(true);
    expect(out.canDelete.allowed).toBe(true);
  });

  it("denies others", () => {
    const out = mountSkill(makeSkill({ created_by: "u-2" }), "member");
    expect(out.canEdit.allowed).toBe(false);
    expect(out.canEdit.reason).toBe("not_resource_owner");
    expect(out.canDelete.allowed).toBe(false);
  });
});
