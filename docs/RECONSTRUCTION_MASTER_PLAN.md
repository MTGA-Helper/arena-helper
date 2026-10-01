# Reconstruction Master Plan — Arena Helper

## Core Principle
**The project did not fail. The project fragmented.**

Multiple functional subsystems evolved independently across distinct environments:
- **Platform World:** Live Render infrastructure, Docker configs, health checks, telemetry, and upgrade advisors.
- **Portal World:** Standalone FastAPI application (user-portal/) handling user registration, login, and JWT token creation.
- **Intelligence World:** Local recovery modules managing CSV collection imports, relational card databases, Scryfall bindings, structural deck scoring, wildcard craft prioritization, and recommendation algorithms.
- **Historical UI World:** Visual session evidence, screenshots, and Swagger outputs dictating expected user workflows and dashboards.

This reconstruction effort reunites these systems into a single deployable platform without recreating functionality that already exists.

## Reconstruction Phases
1. **Phase 1: Documentation Lockdown** — Establish audit-grade capability matrices, architecture reassembly flows, and historical evidence logs on dev.
2. **Phase 2: Create The Unification Branch** — Spin up sandbox/unified-platform to merge Platform, Portal, and Intelligence worlds.
3. **Phase 3: Tiered Integration** — Systematically wire subsystems in priority order: Auth/User Model $\rightarrow$ Collection $\rightarrow$ Deck Analysis $\rightarrow$ Recommendations $\rightarrow$ Match Telemetry.
