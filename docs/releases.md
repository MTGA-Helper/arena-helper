# Releases and branches

## Branch strategy

- `main` is the stable foundation branch.
- `telemetry-integration` contains telemetry and analytics work.
- Feature work is committed on `telemetry-integration` and should be pushed
  only when a release or review explicitly requires it.

## Current verified state

Repository: `https://github.com/owlensteed/arena-helper.git`

| Milestone | Commit | Tag/remote status |
|---|---|---|
| Foundation | `54a2ae4fc43ae509ac24665d0121586f379215e5` | `v0.1.0-foundation`, pushed |
| Telemetry | `2c1e8c453854994aab74cf45a33559c0c6009f89` | `v0.2.0-telemetry`, pushed |
| Packaging cleanup | `f3c71f1184afdf73f056f059fc6d880f3e27958d` | local commit, not tagged or pushed |
| Analytics | `fb26f8643c842024bee3ed17b7fd7b519470a654` | local commit, not tagged or pushed |

At the time this documentation was written, local
`telemetry-integration` is two commits ahead of
`origin/telemetry-integration`. The analytics commit has no release tag.

## Release limitations

The package metadata currently says version `0.2.1`, while the latest local
feature milestone is the untagged analytics commit. No automated release
workflow, changelog, migration process, or CI configuration is present.
