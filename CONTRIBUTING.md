# Contributing

Thanks for helping. Read [`docs/design.md`](docs/design.md) first: it explains the layers
and why things are the way they are. A change that contradicts the design starts by
changing the design, in its own PR.

## Setup

You need Python 3.14 and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/rubidium-labs/discord-bot-core.git
cd discord-bot-core
uv sync                  # creates .venv, installs the library and the dev group from uv.lock
```

## Checks

CI runs the same commands on every PR. Run them before you push:

```bash
uv run pytest            # tests; coverage is reported (term + xml), no fail_under threshold
uv run ruff check        # lint
uv run ruff format       # format (CI runs `ruff format --check`)
uv run mypy src          # type check (the package ships py.typed)
```

Tests never need Discord or the network: use the fakes in `discord_bot_core.testing`
(see [docs/testing.md](docs/testing.md)). `uv.lock` is committed; change dependencies
with `uv add` / `uv lock` and commit the lock file in the same PR.

## Code rules

- Type hints everywhere; the package ships `py.typed` and CI runs mypy.
- Docstrings in **Google style** on every public class and function, with an example when
  the use is not obvious. Ruff enforces this with the `D` rules (`convention = "google"`).
- Log with lazy arguments (`logger.info("x %s", x)`), never f-strings. No bare `except`,
  use `raise` and not `raise e`.
- No module-level singletons, no `os.getenv`, no hard-coded ids (see design section 1).
- `infrastructure/` imports no `discord`; `ui/` never touches the database.
- Code, comments and docs are in English. Docs are part of the PR that changes the
  behaviour they describe. Never commit a token, even an expired one.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/): `type(scope): summary`, in
the imperative, e.g. `feat(settings): add CoreSettings`, `fix(db): rollback on cancel`,
`docs: explain secrets_dir`, `chore(deps): bump uv.lock`. Types: `feat`, `fix`, `docs`,
`test`, `refactor`, `chore`, `ci`. Mark a breaking change with `!` or a
`BREAKING CHANGE:` footer.

## Pull requests

- **Small PRs**: one step of the implementation plan (design section 17) or one fix.
- Tests and docs in the same PR; update `CHANGELOG.md` under `## [Unreleased]`.
- **Review by a worker that did not write the PR.** The author does not merge.
- CI (pytest with coverage, ruff check, ruff format check) must be green.

## Releases

Versions follow [SemVer](https://semver.org/). While `0.x`, a minor release may break the
public API (what `discord_bot_core.__all__` and the documented modules expose); say so in
the changelog.

The maintainer releases:

1. In a release PR, move the `Unreleased` entries of `CHANGELOG.md` under a new
   `## [X.Y.Z] - YYYY-MM-DD` heading and update the compare links at the bottom.
2. Merge it. Check CI is green on `main`.
3. Create an **annotated** tag on the merge commit and push it:
   `git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin vX.Y.Z`.
4. Apps depend on the tag (git dependency, see
   [getting started](docs/getting-started.md)) and bump it in their own PR.

Never move or delete a published tag; release a new patch instead.
