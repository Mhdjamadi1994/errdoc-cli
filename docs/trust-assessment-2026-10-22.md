# errdoc trust assessment

**Reviewed:** October 22, 2026  
**Package version:** `0.1.0` (pre-release)  
**Overall readiness score:** **5/10**

This is an engineering judgment for this release candidate, not a security certification or a guarantee that an explanation is correct. The score weighs observed diagnosis quality and open release checks more heavily than test count. The full human response report is kept locally under `.errdoc/` because it contains raw model answers; this page records only aggregate results and the specific public-safe findings.

## Evidence behind the score

| Area | Score | Evidence and limit |
| --- | ---: | --- |
| Command and sandbox controls | 8/10 | The model does not execute suggestions. The optional fix runner asks before execution, previews a bounded file manifest, and runs in a temporary container configured without network access, with a read-only root and an unprivileged user. Three local Docker integration tests passed. This does not prove resistance to every host or runtime escape. |
| Diagnosis quality | 3/10 | Human review covered all 51 current `llama3.2` answers: mean score 9.39/10, but only 1/51 was labeled `correct` and 50/51 `partially-correct`. That is 1.96% fully correct, far below the 90% gate. The high numeric mean records the reviewer's dimension scores; it does not override the separate correctness labels. |
| Output quality checks | 5/10 | The reviewed set had zero detected unsafe suggestions and zero command suggestions, but one unsupported claim and one answer longer than 120 words. The unsupported answer says an HTTP 503 service will return after exactly 45 seconds; `Retry-After: 45` does not prove recovery at that time. The overlong answer is `extended_sqlalchemy_missing_greenlet` (132 words). |
| Build and CI evidence | 7/10 | Windows Python 3.11 and 3.14 each passed 343 tests with three integration tests deselected; the separate Windows Docker run passed all three integration tests. GitHub Actions run `39797206973` for commit `f58bc45` completed successfully. Local test results do not substitute for testing every supported host and configuration. |
| Release and privacy readiness | 3/10 | Artifacts were locally built and checked in prior candidate work, but TestPyPI publishing and clean-index installation have not been completed. PyPI name ownership is unverified. Secret filtering and snapshot selection are heuristic and need a complete human review. Branch/tag protections are not confirmed. |

## What is working well

- errdoc does not execute model-proposed commands. The optional runner takes a command supplied by the user and requires confirmation after showing a snapshot manifest.
- The documented snapshot has size and file-count bounds; symlinks, reparse points, special files, common credential files, logs, and build output are excluded. Users are told that secrets inside ordinary source files can still pass through and must inspect the preview.
- Local Ollama and remote-provider data flows are described separately. Remote requests contain sanitized error text and limited context; sanitization is explicitly described as best effort.
- CI covers Windows, Linux, and macOS across Python 3.10 through 3.14. The release workflow builds reviewable artifacts and has a separately gated TestPyPI publishing job; no production PyPI upload job is configured.
- The regression corpus exercises command filtering, privacy handling, archive paths, and sandbox behavior. Those tests establish behavior for their fixtures, not universal safety.

## What prevents a higher score

1. The current human-reviewed answer set misses the exact-correct threshold by a wide margin: 1/51 rather than at least 90%. Keep the individual review labels as entered; do not relabel them merely to pass a release gate. Improve the answers, generate a new set, and review that exact set again.
2. The current answers include an unsupported recovery-time claim and a response beyond the stated length limit. Both need to be corrected in generated/user-visible output and covered by regression checks before a new model evaluation.
3. TestPyPI Trusted Publishing is not yet configured and no TestPyPI install has been verified. The normalized PyPI project name and production release ownership are also unverified.
4. Redaction and file selection cannot guarantee detection of secrets in arbitrary text. A user must inspect the snapshot manifest before approval; current automated checks cannot replace a full human privacy review.
5. GitHub branch and release-tag protections and required reviewers for production publishing remain unverified.

## Release decision

**Do not call this a trusted public release or publish it to production PyPI yet.** The source can be reviewed and tested from GitHub, but the beta diagnosis gate is not met. The 9.39/10 mean is not a reliability pass: only one answer received the `correct` classification. The separate automatic and release blockers are also still present.

The next evidence needed is: resolve the current-answer quality failures, run a fresh evaluation after any prompt or filtering change, repeat human review on that exact output, complete the snapshot/privacy review, configure and test TestPyPI Trusted Publishing, and confirm the release protections. Recalculate this score only from those new results.
