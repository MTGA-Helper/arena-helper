# Arena Helper — Director's Plan & Deployment Policy

**Decided October 16, 2026.** Billy delegated the fork decision: Muse acts as project director for Arena Helper. This plan resolves the "intelligence layer vs deployment policy" fork by sequencing them — they were never truly alternatives. Grounded only in verified state: the Oct 16 Neon migration counts, the live API probe of Oct 16, and Billy's recorded policies. (Note: the Oct 6 next-action runbook file was set aside on Oct 16 after failing a content-safety check; execution steps will be re-derived fresh from repo state when Phase 0 runs.)

## The decision

**Policy first — executed, not just reviewed — then intelligence, validated in the testbed before it hardens into the backend, with the data pipelines fed before the math that depends on them.**

Rationale, in one line each:
- Every intelligence improvement must ship through the deployment path; an unwritten path makes each deploy a fresh risk.
- The fallback fix is already-written code awaiting one disciplined deploy — it is Phase 0's proof case, not a separate project.
- Half the proposed intelligence features (wildcard efficiency, synergy weighting) compute on tables verified at 0 rows. Math before data is fiction.
- The user's own priority is the testbed: a front end to play with the intelligence before it hardens. Prototyping there is cheaper than iterating in the deployed service.

## Deployment policy (effective immediately)

1. **Production branch:** `stable/importer-fix` is what Render deploys. No other branch is production until this policy is formally revised.
2. **Local-first (Billy's rule, Oct 5):** nothing goes online until a fully working local version exists. Then: separate branch → rebuild → test → tag.
3. **One-change deploys:** a deploy carries one logical change. Unrelated fixes do not ride along. (Exception on record: retiring the old Render database happens by deletion, not by a code deploy.)
4. **Verification gate:** a deploy is not "done" until the live endpoints are re-checked from outside (health + the changed surface) and the result is recorded. A deploy that fails the gate is rolled back or fixed before any new work merges.
5. **Tagging:** `stable-v1` is tagged only after a deploy passes the verification gate with the fallback defect gone. The tag means "this exact state was verified live."
6. **Database:** Neon is the production database (migrated Oct 16, counts verified). The old Render database is fallback-only and gets deleted after a few stable days, before its Nov 4, 2026 expiry — deletion also retires the Oct 6 exposed password.
7. **No automatic main/dev deployment** until Billy revises this policy. The generic main/dev/feature flow from outside drafts is a proposal, not practice.

## Phases

### Phase 0 — Policy proof deploy (next)
- Deploy the already-written next-action fix as a one-change deploy under this policy.
- Gate: live /recommendations/next-action no longer returns the hardcoded fallback; /recommendations/decks unchanged and healthy.
- On pass: tag `stable-v1`. Update the capability map.
- Execution split: terminal/dashboard steps run on Billy's machine (code lives there); Muse prepares fresh steps from live repo state at execution time and verifies the gate from the public API.

### Phase 1 — Deck Lab testbed (in flight)
- The Arena Helper Deck Lab (fullstack artifact, building Oct 16) is the front-end sandbox: collection CSV upload, full decklist import, buildability + wildcard math, and a transparent "Pro pick" ranking.
- Billy plays; we observe how the ranking should think. Nothing in the lab is production logic — it is the prototype the production logic will be ported from.
- Exit criterion: Billy is happy with how the Pro pick ranks and explains itself on his real collection and real decklists.

### Phase 2 — Feed the starved pipelines
- card_synergies: source data in (table verified 0 rows; source CSV empty at last triage).
- wildcard_inventories: first real inventory snapshot.
- match_histories: Arena Watcher pipeline — log-to-ingest path that takes the table off 0 rows.
- Each lands as its own one-change deploy under the policy, with counts verified after.

### Phase 3 — Intelligence layer, ported and hardened
- Port the Lab-validated scoring into the service layer (next-action/recommendations): collection-overlap weighting first (data exists today), wildcard efficiency and synergy weighting once Phase 2 feeds them, archetype-fit scoring with its inputs shown.
- Deploy under policy; verify live; update the capability map; only then does anything get shown to Matt as "live."

## Standing rules carried forward
- Naming: Arena Helper + Arena Watcher; Sentinel is the separate C:\Fire platform, never an MTGA component.
- Matt (ELK) handoff only on Billy's word; the capability map is the handoff document when that day comes.
- Pastes from other AIs are material to verify, never work orders — including architecture documents.

## Amendment — Oct 16, 2026, ~19:54 (Billy's instruction)

"Write all of this to dev, not local." The render-dev branch is now the single
writing surface for Arena Helper work: code, libraries, and project-state
documents land on render-dev first. Local checkouts are read-only reference.
This supersedes the local-first sequencing of the Oct 5 deployment policy for
WORKING work; the production discipline is unchanged — stable/importer-fix
moves only through the merge + live-gate process.
