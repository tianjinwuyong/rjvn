# Implementation Plan: Plant Manager Apps Closed Loop

## Overview
Complete the unified PDA plant-manager workspace for the Vietnam factory. Senior and
junior plant managers share the same operational pages, while senior-only release actions
remain protected by MES permissions. All pages must show live MES state and make the next
action obvious on a PDA-sized screen.

## Architecture Decisions
- MES remains the source of truth; the PDA only requests and displays actions.
- Seniority is carried with the authenticated user and is not inferred from the display name.
- Junior managers can inspect and coordinate; final release/authorization remains senior-only
  until the business owner explicitly approves a broader delegation.

## Task List

### Phase 1: Identity and access foundation
- [ ] Persist plant-manager seniority in the authenticated user model and quick-login session.
- [ ] Display the manager name, role, and seniority in the cockpit header.
- [ ] Gate plant-manager mutation controls by the MES permission `approval.final.release`.

### Phase 2: Operational pages
- [ ] Verify the plant-manager dashboard exposes alerts, line status, team, targets,
      decisions, loading, HR, communication, assignments, hiring, grievance, and profile.
- [ ] Verify plant-manager approval and exception pages remain reachable from the dashboard.
- [ ] Keep junior pages read/review oriented and show a clear reason when an action is locked.

### Checkpoint: PDA build
- [ ] Assemble the plant-manager APK.
- [ ] Verify quick login identities and permission differences with focused unit tests.

## Open Questions
- Should a junior plant manager be allowed to create PMC work orders and authorize exceptions,
  or remain review-only? Default for this implementation: review-only for final approval and
  exception authorization; WO creation remains visible but can be restricted by MES response.

## Definition of done
- Both manager identities enter the same complete cockpit.
- Seniority is visible and survives quick login/session serialization.
- Junior cannot submit final approval/exception authorization from the PDA.
- Build completes and test evidence is reported without claiming a failing test runner passed.
