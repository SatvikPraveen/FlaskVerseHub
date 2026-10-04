# Contributing

Thank you for considering a contribution. This project values correctness,
measurability and clear documentation over feature count.

## Development setup

```bash
./scripts/bootstrap.sh && source .venv/bin/activate
make test lint typecheck security
```

`scripts/check.sh` runs exactly what CI runs.

## Workflow

1. Open an issue (or comment on one) describing the change; for retrieval
   work, state which metric you expect to move and how you will measure it.
2. Branch from `main` (`feature/…`, `fix/…`, `exp/…`).
3. Keep commits focused and write messages in the imperative mood with a
   type prefix (`feat`, `fix`, `refactor`, `test`, `docs`, `ci`, `chore`).
   Explain *why* in the body when it is not obvious.
4. Add or update tests. The coverage gate is 85 % branch coverage; new
   modules should be close to fully covered.
5. Update documentation: `docs/API.md` and the OpenAPI document for API
   changes, an ADR for architectural decisions, `CHANGELOG.md` under
   *Unreleased*.
6. If you touched `app/search` or `experiments`, run `make experiment` and
   commit the regenerated `experiments/results/`; CI fails otherwise.
7. Open a pull request using the template.

## Code conventions

* Python 3.11+, type hints everywhere, mypy clean.
* Business logic lives in service modules; routes and resolvers only
  translate. Every read path starts from `KnowledgeItem.visible_to`.
* Time: use `app.utils.time`; never `datetime.utcnow()`.
* HTML from users goes through `app.security.sanitization`.
* Side effects (audit, notifications, events) are emitted from services via
  `app.services.*`, never from templates or routes.
* Tests: `tests/unit` for logic, `tests/integration` for blueprints,
  `tests/api` for contracts, `tests/research` for the engine. Prefer
  property-based tests for algorithms.

## Reporting security issues

Please follow [SECURITY.md](SECURITY.md) rather than opening a public issue.
