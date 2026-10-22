# errdoc trust assessment

**Reviewed:** October 22, 2026  
**Package version:** `0.1.0` (pre-release)  
**Pre-fix baseline score:** **5/10**
**Updated code trust rating:** **7/10 (provisional; human gate not met)**

This is an engineering judgment, not a security certification or a guarantee that any explanation is correct. The 5/10 score applied to the pre-fix baseline. After focused diagnostics, sanitizer fixes, and regression tests, the updated code merits a provisional 7/10: 366 local tests pass on Python 3.11 and 3.14, and a fresh 51-case Ollama run reported zero failed requests, unsafe or command suggestions, generic advice, unsupported-claim flags, or overlong answers. The automatic fact-coverage heuristic averaged 0.505 and is not a correctness score. The fresh answers have not yet received human ratings, so the project does not meet its human release gate and cannot claim 8/10 trust. The completed baseline scores remain unchanged in the [public score-only CSV](llm-human-review-2026-10-22.csv); the raw answers stay local under `.errdoc/`.

## Evidence behind the score

| Area | Score | Evidence and limit |
| --- | ---: | --- |
| Command and sandbox controls | 8/10 | The model does not execute suggestions. The optional fix runner asks before execution, previews a bounded file manifest, and runs in a temporary container configured without network access, with a read-only root and an unprivileged user. Three local Docker integration tests passed. This does not prove resistance to every host or runtime escape. |
| Diagnosis quality | 5/10 | The only human review currently applies to the pre-fix answers: mean 9.39/10, but 1/51 `correct` and 50/51 `partially-correct`, below the 90% exact-correct threshold. Updated answers need their own human review. |
| Updated output checks | 8/10 | Fresh 51-case `llama3.2` run: zero failed requests, command/unsafe/generic/unsupported-claim/over-120-word flags. Automatic expected-fact coverage averaged 0.505; it is a weak lexical signal and does not establish semantic correctness. |
| Build and CI evidence | 8/10 | Windows Python 3.11 and 3.14 each pass 366 tests; the three Docker sandbox integration tests pass separately. Fresh wheel and sdist pass strict metadata checks and install in separate clean Python 3.14 environments with `pip check` and both entry points working. Hosted CI for the updated commit is still pending. |
| Release and privacy readiness | 3/10 | Artifacts were locally built and checked in prior candidate work, but TestPyPI publishing and clean-index installation have not been completed. PyPI name ownership is unverified. Secret filtering and snapshot selection are heuristic and need a complete human review. Branch/tag protections are not confirmed. |

## What is working well

- errdoc does not execute model-proposed commands. The optional runner takes a command supplied by the user and requires confirmation after showing a snapshot manifest.
- The documented snapshot has size and file-count bounds; symlinks, reparse points, special files, common credential files, logs, and build output are excluded. Users are told that secrets inside ordinary source files can still pass through and must inspect the preview.
- Local Ollama and remote-provider data flows are described separately. Remote requests contain sanitized error text and limited context; sanitization is explicitly described as best effort.
- CI covers Windows, Linux, and macOS across Python 3.10 through 3.14. The release workflow builds reviewable artifacts and has a separately gated TestPyPI publishing job; no production PyPI upload job is configured.
- The regression corpus exercises command filtering, privacy handling, archive paths, and sandbox behavior. Those tests establish behavior for their fixtures, not universal safety.

## Changes after the baseline review

- Added deterministic, command-free diagnoses for concrete cases the baseline and first follow-up model run mishandled, including Java heap and cast/link errors, Python encoding and native-extension initializer errors, Rust borrow/trait errors, asyncio cross-loop use, C/C++ linker symbols, HTTP 503 `Retry-After`, SQLAlchemy `MissingGreenlet`, local socket allocation, Go unresolved identifiers, PHP class lookup, Redis client limits, Kubernetes ConfigMaps, Docker executable format, and npm engine constraints.
- Fixed an IPv6-redaction false positive that was corrupting namespaced identifiers such as `std::fmt::Display` and `TelemetryClient::flush()`. IPv4 and actual IPv6 redaction tests remain in place.
- Expanded the synthetic corpus from 107 to 129 cases while keeping 51 eligible for model evaluation. The added cases cover distinct runtimes and failure families rather than lowering the review sample requirement.
- On the updated worktree, Windows Python 3.11 and 3.14 each passed 366 tests with three integration tests deselected; a separate opt-in Docker run passed all three sandbox integration tests.
- The fresh automatic run for this code is `.errdoc/llm-automatic-post-diagnostics-v2-2026-10-22.json`: 51/51 responses completed; zero failed requests, detected unsafe suggestions, command suggestions, generic-advice flags, unsupported-claim flags, or overlong responses; mean heuristic fact coverage 0.505. It has zero human ratings and the release gate is **NOT MET**.
- Fresh local artifacts in `.errdoc/release-candidate-dist-v21/` both pass `twine check --strict`, install in separate fresh Python 3.14 environments, pass `pip check`, and run `errdoc --version` and `fix --version`. The sdist has 64 members and includes the score-only CSV; neither artifact contains local evaluation reports. SHA-256: wheel `b3191e7f24092fb2bb2886481a8359b648bec19d90f1b89e6df783a7b7e793ef`; sdist `6969bf8418e04826ae9752329a534d095730ebafaf0bb79d25d721173a5531cf`.

The updated code is provisionally **7/10**, not 8/10, until the owner scores the exact 51 new answers and the correctness gate is met. A score will not be raised by copying baseline ratings or by treating automatic keyword checks as human judgment.

## What prevents a higher score

1. The pre-fix baseline human-reviewed set misses the exact-correct threshold: 1/51 rather than at least 90%. Its labels and dimension scores are preserved as entered. They cannot rate the revised answers.
2. The fresh output passes the current automatic wording/safety filters, but none of its 51 answers has been human-rated yet. The new evaluation averages only 0.505 on a lexical fact-coverage heuristic, so manual correctness review is essential.
3. TestPyPI Trusted Publishing is not yet configured and no TestPyPI install has been verified. The normalized PyPI project name and production release ownership are also unverified.
4. Redaction and file selection cannot guarantee detection of secrets in arbitrary text. A user must inspect the snapshot manifest before approval; current automated checks cannot replace a full human privacy review.
5. GitHub branch and release-tag protections and required reviewers for production publishing remain unverified.

## Release decision

**Do not call this a fully trusted public release or publish it to production PyPI yet.** The updated code has improved to a provisional 7/10 and passes the current automatic output filters, but the human correctness gate is still unmet. The old 9.39/10 mean is not evidence for the updated version: only one answer in that old set was marked fully correct.

The next evidence needed is: have the owner review the exact 51 answers saved in `.errdoc/llm-automatic-post-diagnostics-v2-2026-10-22.json`, complete the snapshot/privacy review, configure and test TestPyPI Trusted Publishing, confirm release protections, and run hosted CI for the pushed commit. Recalculate the trust rating only after these checks.
