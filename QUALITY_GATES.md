# errdoc Public Beta Quality Gates

This document records the release requirements for a trustworthy public beta. A feature is not considered complete because code or tests exist; the evidence listed below must be produced before release.

## Release Identity

- GitHub repository: https://github.com/Mhdjamadi1994/errdoc-cli (public repository created October 21, 2026)
- Python distribution name: errdoc-cli (PyPI/TestPyPI ownership and upload access remain unverified)
- Import package and command names: errdoc, with fix as an alias
- License: MIT
- Release channel: GitHub prerelease and PyPI TestPyPI first; production PyPI only after the prerelease is verified

## Quality Gates

### 1. Cross-Platform Compatibility

- [ ] Run the full suite on Windows, Linux, and macOS for Python 3.10 through 3.14 on a fully completed hosted run. On October 21, 2026, the latest run concluded success and all 18 job steps reported success, but GitHub still reports the Windows Python 3.12 job as in progress; confirm the check settles before release.
- [x] Earlier Windows Python 3.11 and Python 3.14.5 runs: 267 passed, 2 integration tests deselected on October 14, 2026.
- [x] After the LLM prompt and corpus updates, full Windows Python 3.14.5 regression suite: 273 passed, 2 integration tests deselected on October 14, 2026.
- [x] After timeout handling was updated to terminate child processes that retain captured pipes, the current Windows Python 3.11 and 3.14.5 suites each passed 291 tests with 2 integration tests deselected on October 15, 2026.
- [x] After the prompt and corpus updates, Windows Python 3.14.5 Docker sandbox integration suite: 2 passed on October 14, 2026.
- [x] Current-revision Linux Python 3.11 container run on October 15, 2026: 291 passed, 2 integration tests deselected, zero warnings/skips. Source and Windows Python 3.11 dependencies were mounted read-only, networking was disabled, and pytest cache was disabled. This is supporting Linux runtime evidence, not native Linux CI or a fresh Linux dependency-install test.
- [x] Current wheel and source distribution each installed with freshly resolved runtime dependencies in disposable Linux Python 3.11 virtual environments on October 15, 2026; `errdoc --version` and `fix --version` returned 0.1.0 for both.
- [x] Current-revision Windows Docker sandbox integration on October 15, 2026: 2 passed on Python 3.11 and 2 passed on Python 3.14.5.
- [ ] Native Linux CI and macOS suite against this exact revision. The local Linux container run is supporting evidence, not a replacement for native runners.
- [ ] Run the Python 3.10, 3.12, and 3.13 matrix entries; those interpreters are not installed locally.
- [ ] Verify command quoting, signal handling, file paths, terminal rendering, and timeouts on each operating system.
- [ ] Keep the release blocked while any required matrix job is red or skipped.

### 2. Diagnosis Quality

- [x] Maintain a diverse 90-case synthetic corpus with 40 deterministic routes and 50 LLM-backed cases spanning Python, Django, Node.js, npm, Git, CMake, Cargo, Docker, shell tools, JSON config, pytest, PostgreSQL, Go, Kubernetes, Terraform, Java, .NET, Windows, databases, and network errors. Case identifiers are regression-tested for uniqueness.
- [ ] Evaluate each model/provider against a documented expected-cause rubric, actionable-step rubric, and unsafe-or-unsupported-command rubric.
- [x] The evaluation report records expected-fact coverage, generic advice, command suggestions, unsafe-command heuristics, and per-response failure state; interactive review records correct/partially-correct/incorrect plus a 10-point score.
- [x] Bound command output to 512 KiB per stream, file logs to 2 MiB, and piped input to 1,000,000 characters; retain the tail and mark omitted earlier output.
- [x] Cap configurable input at the same 1,000,000-character capture limit and cap command/LLM timeouts at 600 seconds.
- [x] The interactive reviewer now sees the original synthetic error and expected evidence groups, and can label unsafe answers separately from incorrect answers.
- [x] The evaluator enforces the public-beta score gate: 50 human ratings, mean >=8.5/10, at least 90% correct, zero incorrect/unsafe, request failures, detected command suggestions, and fixture-specific unsupported claims.
- [x] Located and recorded the completed October 14, 2026 human review: 50/50 ratings for llama3.2, mean 8.4/10; 21 correct (42%), 25 partially correct, 2 incorrect, 2 unsafe; 3 raw command/code suggestions; 0 request failures. The report is local at `.errdoc/llm-human-review-prompt-v3-2026-10-14.json` and fails the gate. Its prompt hash is historical and cannot satisfy the current-prompt gate.
- [x] October 21, 2026 release-candidate evaluation: 50 answers, 0 request failures, 0 unsafe/command/unsupported-claim/generic-advice/overlong flags after recalculating the filter, and 1 bare tool reference tracked separately. The reports are local at `.errdoc/llm-automatic-release-candidate-2026-10-21.json` and `.errdoc/llm-automatic-release-candidate-2026-10-21-metrics.json`. Human review count is 0; the gate remains NOT MET.
- [x] Offline review now displays both raw, untrusted model output and the filtered user-visible answer; human ratings are explicitly about the raw answer and its command/code proposals.
- [x] Link per-case human scores with expected evidence-group coverage; reports expose the mean human score (MOS), mean lexical fact coverage across all cases, and mean coverage over the human-reviewed subset with explicit sample counts.
- [x] Record preliminary human review for llama3.2 on 16 LLM fixtures: mean 9.25/10, 5/16 exactly correct (31.25%), 11 partially correct, zero incorrect, and zero unsafe. This is below the 90% exact-correct gate and is tied to the prior prompt; one Kubernetes answer marked correct included an unsupported claim that restart count 9 was a maximum, so treat the recorded exact-correct rate as unverified.
- [ ] After the current prompt and filter changes, generate and human-review all 50 new LLM-backed responses; do not carry ratings across prompt changes.
- [ ] Require zero unsafe commands in the release evaluation set; require a documented minimum correctness score before release.
- [x] Run live evaluation against the configured local Ollama model: 16 LLM-backed synthetic cases on October 14, 2026, 0 request failures and 41/50 expected-term groups matched (82% heuristic coverage). After refining a broad Node.js phrase check, the re-evaluated outputs had zero automatic unsafe, command, generic-advice, unsupported-claim, or over-120-word flags. This remains a small synthetic, automatic-only run; it does not meet the 50-case-per-model human release gate.
- [ ] Run live evaluation against at least one configured OpenAI-compatible endpoint. Keep network tests opt-in and never require credentials in CI.
- [x] Add credential-free loopback HTTP tests for an OpenAI-compatible endpoint. Verify optional Authorization, configured model/output-token settings, redaction of a synthetic API-key value in request data, endpoint path construction, and bounded rejection of a response larger than 1 MiB. This local test server is not evidence of a live third-party endpoint evaluation.
- [x] Bound successful and error response bodies from configured LLM endpoints to 1 MiB before parsing.
- [x] Never run model output automatically; model-generated command sections are suppressed, and only a user-entered command can reach the separately confirmed sandbox executor.

### 3. Log Compression and Privacy

- [x] Build a 12-case synthetic fixture set with short and long logs, repeated lines, tracebacks, dependency frames, Windows and POSIX paths, and secret-like values.
- [x] Measure original and compressed character counts and approximate token-like units using the documented regex proxy in scripts/benchmark_compression.py.
- [x] Verify required error and redaction markers survive compression for all checked-in synthetic cases.
- [x] Current 12-case synthetic corpus reaches 98.0% aggregate character reduction and 97.9% approximate token-proxy reduction while preserving required markers. This is corpus-specific and is not model-specific tokenization; retain the gate for broader real-world corpora.
- [x] Test truncation boundaries and verify common secrets are redacted on the CLI path before diagnosis/network calls.
- [x] Redact valid IPv4/IPv6 values and common local home-directory paths from displayed logs and model requests; omit the working directory from runtime context.
- [ ] Audit all supported path styles, unusual secrets, and realistic sanitized logs with humans before claiming comprehensive privacy protection.
- [x] Redact quoted multiword credential values and sanitize model text again before terminal display.
- [x] Sanitize CLI error messages and redact the configured API key before displaying provider or configuration errors; regression coverage passes locally.
- [x] Sanitize provider error bodies and redact the configured API key before raising exceptions through the direct Python diagnosis API; regression coverage verifies an echoed credential is not exposed.
- [x] Add regression coverage for cloud secret-key assignments, URL-embedded database credentials, Basic authorization, quoted JSON API-key fields, PEM private-key blocks, and ensure synthetic values are absent from a real loopback HTTP request payload.
- [x] Document that heuristic redaction cannot guarantee detection of every secret.

### 4. Isolated Fix Execution

- [x] Execute proposed fixes only inside an isolated Docker or Podman container; there is no host-execution path.
- [x] Disable fix execution when the sandbox runtime is missing or unhealthy; never silently fall back to host execution.
- [x] Default to no network, a read-only root filesystem, a disposable writable tmpfs project copy, resource limits, and a bounded timeout.
- [x] Reject non-finite and unbounded sandbox timeouts; cap execution at 600 seconds.
- [x] Never mount host credentials, home directories, Docker socket, or the host filesystem into the sandbox.
- [x] Keep the original project read-only by never mounting it; run against a filtered, writable disposable copy and discard all changes after execution.
- [x] Opt-in Docker integration checks verify that a read-only source file is writable only in the disposable copy, original project changes are discarded, the process is unprivileged, a world-writable root-filesystem path rejects writes, and only the loopback interface is visible inside the sandbox on local Windows/Docker.
- [ ] Test sandbox escapes, path traversal, malicious shell syntax, resource exhaustion, and cleanup on Windows, Linux, and macOS. Local unit checks cover symlink filtering, shell-free argv parsing, resource limits, and cleanup; cross-platform escape/resource testing remains open.
- [x] Add a 20,000-entry snapshot cap, existing 10,000-file/64 MiB caps, and a 16,384-character command cap. Test oversized inputs, empty-directory projects, traversal paths, and archive symlink/hardlink entries. Docker integration reads live cgroup limits and confirms 128-process and 1 GiB memory caps.
- [x] Keep Docker/Podman readiness checks bounded at 8 seconds, report health-check timeouts separately from a missing runtime, and keep host execution disabled when health checks fail.
- [x] Explain the sandbox threat model and remaining limits in the README.
- [x] Produce a path-and-size manifest of the exact sandbox snapshot before confirmation; the confirmed run consumes those same archived bytes. The manifest records included files and excluded paths/reasons without file contents.

### 5. Packaging, Documentation, and Security

Artifact freshness note (October 21, 2026): historical `dist` files are stale. The current version 0.1.0 wheel and sdist were rebuilt from the reviewed commit in `.errdoc/release-candidate-dist-v11/`, checked, clean-installed, and scanned. They remain review candidates and have not been uploaded.

- [x] MIT license file added.
- [ ] Verify package name availability and ownership on PyPI before a release.
- [ ] A read-only request to `https://pypi.org/pypi/errdoc-cli/json` returned HTTP 404 on October 16, 2026, so no project was listed under this name at that time. This does not guarantee that the name is claimable or reserved for this project; recheck and confirm eligibility immediately before TestPyPI or production publication.
- [x] Rechecked the PyPI and TestPyPI JSON endpoints on October 21, 2026; both returned HTTP 404 for `errdoc-cli`. This confirms no public project record was returned at that time, not that PyPI has authorized this maintainer to claim the normalized name.
- [x] Set package author and maintainer metadata to `Mhdjamadi1994` and confirmed canonical repository, Issues, and Security URLs for `https://github.com/Mhdjamadi1994/errdoc-cli`.
- [x] Rebuilt the current wheel and sdist from commit `ae3aabc` using isolated build environments. `twine check --strict` passed; separate clean Python 3.14 installs passed `pip check`, `errdoc --version`, and `fix --version`. The sdist includes the score-only human review CSV and excludes local raw reports. Heuristic scan matches are synthetic private-key examples in regression tests, not real credentials; scan limitations remain.
- [x] Verify from-scratch installation and review both current artifacts independently.
- [ ] Independently review human privacy of all fixtures and the exact release contents before publishing.
- [x] Audited the artifact's five pinned runtime dependencies with pip-audit on October 16, 2026 in a fresh Python 3.11 environment; no known vulnerabilities were reported. CI repeats the audit from a separate target directory so it excludes pip/setuptools bootstrap packages and errdoc-cli itself, which is not published on PyPI.
- [x] Provide Windows, macOS, and Linux development install instructions and an end-to-end local Ollama example.
- [x] Document local and remote LLM data flow, configuration, known limitations, and safe-use boundaries.
- [x] Add contribution, security reporting, and issue-reporting guidance.
- [x] Add an interactive human-review rubric and explicit beta diagnosis thresholds in LLM_REVIEW_GUIDE.md.
- [ ] Complete human privacy review of all fixtures and release contents. Automated scans of the current artifacts found no real credential markers or machine-specific paths; the sdist does include clearly synthetic credential examples for tests.

### 6. Release and Public CI Evidence

- [x] Published 46 intended source, tests, workflow, and documentation files to the public GitHub repository. Local evaluation reports, virtual environments, and distribution artifacts are excluded. Comprehensive human privacy review remains open.
- [ ] Protect the GitHub release workflow and configure branch/tag protections.
- [x] Configure weekly Dependabot updates for Python and GitHub Actions and enable automated Dependabot security updates; regression coverage verifies both update ecosystems.
- [x] Add regression checks that the workflow declares 3 operating systems x 5 Python versions, read-only contents permission, explicit integration selection, installs/smoke-tests both wheel and source distribution, and includes a runtime dependency audit job.
- [x] Pin every third-party GitHub Action to a full commit SHA; the current checkout/setup-python refs were resolved from their upstream tags and have a regression check against mutable version tags.
- [x] Add a non-publishing release-build workflow that tests, builds, checks metadata, and stores reviewable artifacts with read-only repository permissions. It has no PyPI upload step and no OIDC token permission.
- [ ] Configure protected `main` and `v*` tags, required CI status checks, and required reviewers for a dedicated `pypi` environment. An automatic approval review rejected the attempted protection API change because the bypass role was not verified; no alternate route was used.
- [ ] Configure a TestPyPI Trusted Publisher and run the build-only workflow, inspect its exact artifact, then approve a separate TestPyPI upload. No `.pypirc` or PyPI credentials are present locally.
- [x] Enable GitHub private vulnerability reporting on October 21, 2026; SECURITY.md points to its private intake route.
- [x] Verify GitHub secret scanning, push protection, and Dependabot security updates are enabled; repository workflow token defaults to read-only and workflows request only read permissions.
- [ ] Retain a fully settled successful GitHub Actions run for the latest commit; the October 21 run concluded success and its Podman sandbox job succeeded, while GitHub's Windows Python 3.12 job status remains in progress.
- [ ] Publish a GitHub prerelease tag only after all quality gates pass.
- [ ] Publish to TestPyPI, install and smoke-test it from a clean environment, then review the public release contents.
- [ ] Ask the project owner to approve the final public GitHub and production PyPI publication after reviewing the exact release artifacts.
- [ ] Do not describe the project as fully verified until the cross-platform CI and release checks above are complete.

## Current Status

On October 16, 2026, Windows Python 3.14.5 and 3.11.9 each passed all 311 tests with the three Docker integration tests enabled before the latest runtime-error wording test. The integration run verified disposable writes, read-only root filesystem, non-root identity, disabled network, process limit, memory limit, and cleanup. Linux Python 3.11 in a local container passed 308 non-integration tests with source/dependencies read-only and networking disabled before the latest test. New regression checks cover bounded project entries and command length, hostile archive traversal and archive links, a credential-free local OpenAI-compatible HTTP server including oversized response handling, and redaction of cloud keys, URL credentials, Basic auth, JSON credentials, and PEM private keys. Concurrent Ollama/Docker runs caused Docker health checks to time out; one integration attempt still failed with a 20-second probe. The probe remains bounded at 8 seconds and now identifies timeout distinctly. All three integration tests passed when run without concurrent Ollama work. These are local results, not hosted CI or native Linux/macOS results. No live third-party OpenAI-compatible endpoint was contacted; human review of broader log/path privacy remains open.

The project remains a pre-release development build. The public repository is `Mhdjamadi1994/errdoc-cli` and private vulnerability reporting is enabled. Commit `1dbcae9` passed all 15 OS/Python matrix jobs, Docker sandbox, and dependency audit; Podman sandbox failed because Podman 4.9 emitted a bare 64-character image ID. Commit `b948912` normalized this form and added regression coverage; its follow-up found a separate invalid `/var/tmp` read-only assertion, corrected in `36aff18`. The latest hosted workflow on `36aff18` concluded success; all 18 job steps reported success, but GitHub continues to return the Windows Python 3.12 job as in progress, so its settled status needs confirmation. The local Windows suite on October 21, 2026 passed 322 tests with 3 integration tests deselected; Docker sandbox integration passed all 3 tests. A Linux Python 3.11 container run with project/dependencies mounted read-only, networking disabled, and isolated temporary storage passed 321 tests (3 deselected) before the image-ID fix. The hosted matrix covers Windows, Linux, and macOS on Python 3.10 through 3.14. The 90-case diagnosis corpus contains 40 deterministic and 50 LLM-backed cases. An October 14 human review of an older prompt failed the gate (8.4 average, 42% correct, 2 incorrect, 2 unsafe, 3 raw command/code suggestions); it remains historical evidence only. The October 21 candidate completed 50 local Ollama answers with 0 request failures. Rechecking after the filter change found 0 command/code, unsafe, generic-advice, unsupported-claim, or over-120-word flags; one bare tool reference is tracked separately. It has 0 human ratings and still needs independent review. Expected-term coverage is a lexical heuristic, not semantic accuracy. The gate requires 50 human ratings for the exact current model/prompt, mean >=8.5/10, >=90% correct, zero incorrect/unsafe, zero request failures, and zero detected command/unsupported-claim cases. The offline review displays raw and filtered answers and checkpoints every rating. The only OpenAI-compatible endpoint evidence is a credential-free loopback HTTP test server; no live third-party endpoint was contacted. Model output is never executed automatically; user-entered fixes run only in a disposable Docker/Podman sandbox after confirmation. The current wheel and sdist have passed strict metadata checks and clean Windows installs with `pip check` and both CLI smoke tests; final artifact hashes are retained locally with the release evidence. PyPI/TestPyPI upload access and package-name ownership remain unverified. Protected release tags/main, current-prompt human review, TestPyPI upload/install, broader sandbox escape review, live optional-endpoint evaluation, and production package release remain open. Compression reductions (98.0% characters and 97.9% token proxy) apply only to synthetic fixtures.

## Release candidate verification (October 21, 2026)

- Windows Python 3.14.5 and 3.11.9: 322 passed each, 3 integration tests deselected after the image-ID regression test was added.
- Linux Python 3.11 container: 321 passed, 3 deselected, with project/dependencies mounted read-only, networking disabled, and temporary storage isolated. This is not native Linux CI.
- Windows Docker sandbox integration: 3 passed. Podman 6.1.4 is installed and an isolated Hyper-V machine was initialized using the digest-verified image and `volumes=[]`; starting it requires a fresh Windows logon or administrator session.
- The current wheel and source distribution passed `twine check --strict`; each artifact installed in a fresh Python 3.14 environment, `pip check` passed, and both `errdoc --version` and `fix --version` returned 0. The sdist contains the 50-row score-only CSV and excludes private raw review reports.
- `twine check --strict` passed for both v4 artifacts. Each installed from its local file in a separate fresh Python 3.14 environment; `pip check`, `errdoc --version`, and `fix --version` passed for both.
- `git diff --check` passed. A targeted scan of text members inside both artifacts found no workspace/user profile paths or common token-pattern matches; this scan is heuristic and is not a guarantee that an artifact contains no sensitive information.
- The release candidate is not approved for package publication: the current LLM answer set has 0 human scores; branch/tag protection and TestPyPI upload/install verification remain open. GitHub's automatic approval review rejected the requested protection-settings API operation because its hard-coded bypass role was unverified; the operation was not retried through another route. The source is public on GitHub. No PyPI/TestPyPI package upload occurred.
