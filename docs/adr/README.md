# Architecture decision records

Each record captures one decision with lasting consequences: the context,
the options considered, the choice and its trade-offs. Records are
immutable; supersede them with a new record rather than editing history.

| # | Decision | Status |
|---|---|---|
| [0001](0001-modular-monolith-with-service-layer.md) | Modular monolith with a shared service layer | Accepted |
| [0002](0002-typed-sqlalchemy-and-utc-datetimes.md) | Typed SQLAlchemy 2.0 models and UTC-normalised timestamps | Accepted |
| [0003](0003-visibility-policy-on-the-model.md) | Visibility policy expressed once on the model | Accepted |
| [0004](0004-first-principles-retrieval-engine.md) | First-principles retrieval engine over a search service | Accepted |
| [0005](0005-synthetic-benchmark-with-reproducibility-gate.md) | Synthetic benchmark with a CI reproducibility gate | Accepted |
| [0006](0006-dual-api-authentication.md) | JWT bearer tokens and hashed API keys for the API | Accepted |
| [0007](0007-negotiated-error-representation.md) | Negotiated error representation with request ids | Accepted |
| [0008](0008-ruff-mypy-pyproject-toolchain.md) | Single pyproject-based toolchain (ruff, mypy, pytest) | Accepted |
