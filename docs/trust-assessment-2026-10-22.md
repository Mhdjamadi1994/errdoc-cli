# errdoc trust assessment

**Reviewed:** October 22, 2026  
**Package version:** `0.1.0` (pre-release)  
**Pre-fix baseline score:** **5/10**
**Updated code trust rating:** **6/10 (human release gate not met)**

This is an engineering judgment, not a security certification or a guarantee that any explanation is correct. The 5/10 score applied to the pre-fix baseline. The updated code adds deterministic diagnoses, privacy-filter fixes, regression tests, and cross-platform CI. The owner has now rated all 51 answers from the updated `llama3.2` evaluation: mean dimension score 9.29/10, with 0 labeled `correct`, 51 `partially-correct`, 0 `incorrect`, and 0 `unsafe`. The 9.29 average is not an accuracy rate; the separate exact-correct gate is 0%, well below 90%. Automatic checks found no command/unsafe suggestions, generic-advice flags, unsupported claims, or overlong answers, but their 0.505 lexical fact coverage is not semantic proof. The current overall rating is therefore **6/10**: tested software and output safeguards are strong, but the reviewed answer set has not earned a diagnosis-reliability pass. The earlier baseline scores remain in the [baseline score-only CSV](llm-human-review-2026-10-22.csv); the new review is in the [updated score-only CSV](llm-human-review-post-diagnostics-v2-2026-10-22.csv). Both raw reports stay local under `.errdoc/`.

## Evidence behind the score

| Area | Score | Evidence and limit |
| --- | ---: | --- |
| Command and sandbox controls | 8/10 | The model does not execute suggestions. The optional fix runner asks before execution, previews a bounded file manifest, and runs in a temporary container configured without network access, with a read-only root and an unprivileged user. Three local Docker integration tests passed. This does not prove resistance to every host or runtime escape. |
| Human-reviewed diagnosis quality | 3/10 | The updated 51-answer set has mean component score 9.29/10, but every response was classified `partially-correct`: 0/51 fully correct. Dimension means: accuracy 3.82/4, specificity 1.86/2, safety 1.78/2, concision 1.82/2. The 90% exact-correct gate is not met. |
| Automatic output checks | 8/10 | Fresh 51-case `llama3.2` run: zero failed requests, command/unsafe/generic/unsupported-claim/over-120-word flags. Automatic expected-fact coverage averaged 0.505; it is a weak lexical signal and does not establish semantic correctness. |
| Build and CI evidence | 9/10 | Windows Python 3.11 and 3.14 each pass 366 tests; the three Docker sandbox integration tests pass separately. Fresh wheel and sdist pass strict metadata checks and install in separate clean Python 3.14 environments with `pip check` and both entry points working. All 18 hosted GitHub Actions jobs passed in run `39824857961`. |
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
- Fresh local artifacts in `.errdoc/release-candidate-dist-v22/` both pass `twine check --strict`, install in separate fresh Python 3.14 environments, pass `pip check`, and run `errdoc --version` and `fix --version`. The sdist has 65 members and includes both score-only CSVs; neither artifact contains local evaluation reports. SHA-256: wheel `b171e65300d05e8feef608eeb966118f7f8f6867be2565acfac5606de7bebfdb`; sdist `41b3951a9815d0b6966314ace13dd79877b4c76c2cd8e8b7ad32ef8e18187085`.
- The owner completed offline human review of the same 51 updated answers. The score-only export preserves the entered ratings; all 51 labels are `partially-correct`, mean 9.29/10, and none are `correct`, `incorrect`, or `unsafe`. The JSON report does not contain per-case reviewer comments, so the aggregate alone cannot name a single shared reason for the partial labels.

The updated code is **6/10**, not 8/10. The review is complete, but the human correctness gate is not met. A high component-score average or clean automatic checks cannot override the entered 0/51 exact-correct result.

## What prevents a higher score

1. The updated human-reviewed set misses the exact-correct threshold: 0/51 rather than at least 90%. Scores and labels are saved as entered in the score-only export.
2. The dimension-score mean is high, but the reviewer marked all 51 responses partially correct. The report records no written reason per answer; inspect the paired responses and expected-fact rubric before attributing the pattern or changing labels.
3. TestPyPI Trusted Publishing is not yet configured and no TestPyPI install has been verified. The normalized PyPI project name and production release ownership are also unverified.
4. Redaction and file selection cannot guarantee detection of secrets in arbitrary text. A user must inspect the snapshot manifest before approval; current automated checks cannot replace a full human privacy review.
5. GitHub branch and release-tag protections and required reviewers for production publishing remain unverified.

## Release decision

**Do not call this a fully trusted public release or publish it to production PyPI yet.** The updated code is rated 6/10: all 51 reviewed answers are partially correct, so the human correctness gate is unmet even though the mean component score is 9.29/10 and automatic filters are clean. The old 9.39/10 mean belongs to a different answer set and cannot replace these results.

The next work is to address the concrete gaps behind the 51 partial classifications, generate a new answer set, and repeat the human review without changing these ratings. Also complete the snapshot/privacy review, configure and test TestPyPI Trusted Publishing, and confirm release protections before reconsidering the rating.
