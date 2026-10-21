# Contributing to errdoc

Thanks for helping improve errdoc. The project is not yet a verified public release; review QUALITY_GATES.md before proposing release-related changes.

## Development setup

```sh
python -m venv .venv
python -m pip install -e ".[test]"
python -m pytest -q -m "not integration"
```

The default pytest configuration excludes the separately marked Docker integration tests, so unit/regression runs do not report skips. Run those integration checks explicitly with Docker or Podman available:

```sh
ERRDOC_RUN_SANDBOX_INTEGRATION=1 python -m pytest -m integration -q
```

Please add regression tests for bug fixes. Keep source code, fixtures, and documentation in English. Use synthetic logs only; never commit private logs, API keys, tokens, personal paths, or machine-specific configuration.

## Changes

- Keep changes focused and explain user-visible behavior.
- Do not weaken the sandbox, secret-redaction, or model-output quality gates to make a test pass.
- Add representative fixtures when changing compression or diagnosis behavior.
- Do not claim cross-platform support based only on Windows results; include the CI matrix result.
- Never execute LLM-proposed commands directly on the host.

## Pull requests

Include a concise problem statement, implementation summary, test results, and any limitations. A pull request is not release approval.
