# Releasing

The maintainer (Tim) releases; contributors never tag or push to `main`.

Versions follow [SemVer](https://semver.org/). While the version is `0.x`, a minor
release may break; breaking changes are listed under **Changed** or **Removed** in the
changelog.

1. In a release PR, move the `Unreleased` entries of `CHANGELOG.md` under a new
   `## [0.1.0] - <YYYY-MM-DD>` heading (Keep a Changelog format).
2. Merge the PR. CI runs the full suite, ruff and mypy on it.
3. Create an **annotated** tag on the merge commit and push it:
   `git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin vX.Y.Z`.
4. The signed tag triggers the prod deploy workflow. Apps depend on the tag (git
   dependency, e.g. `discord-bot-core @ git+https://github.com/rubidium-labs/discord-bot-core@v0.1.0`),
   or on `main` via a commit-pinned dependency for pre-releases.

Never move or delete a published tag; release a new patch instead.
