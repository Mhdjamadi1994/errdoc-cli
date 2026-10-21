# errdoc

`errdoc` is a cross-platform command-line error analyzer. It captures failed command output, removes common traceback noise, redacts common credential patterns, detects basic project context, and can ask a local Ollama model or an OpenAI-compatible endpoint for a concise diagnosis.

The PyPI distribution is named errdoc-cli; it installs the errdoc command and the shorter fix alias.

## Requirements

- Python 3.10 or newer
- Ollama running locally, or an OpenAI-compatible chat completions API

## Install

After the first verified PyPI release, install the distribution with:

```sh
python -m pip install errdoc-cli
```

The package is not published yet. For development, install from this checkout as shown below.

From this directory, create and activate a virtual environment, then install the project:

```sh
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

macOS or Linux:

```sh
source .venv/bin/activate
python -m pip install -e .
```

### Local Ollama

Install [Ollama](https://ollama.com/download) using its official installer and make sure its local service is running. On Linux, start the service with the method used by your installation. Download a model separately; for the default model:

```sh
ollama pull llama3.2
errdoc python -c "import missing_module"
```

The first analysis may take longer while the model loads. Ollama requests go to the configured local URL by default. The `ollama pull` command downloads model data; errdoc itself does not download models.

### OpenAI-compatible endpoint

Set the provider, endpoint, model, and key in `~/.errdoc/config.json` or the matching `ERRDOC_*` environment variables, then run errdoc normally. Example configuration:

```json
{
  "provider": "openai",
  "model": "your-model-name",
  "base_url": "https://your-provider.example/v1",
  "api_key": null,
  "timeout": 180,
  "max_input_chars": 12000,
  "max_output_tokens": 256
}
```

Set `ERRDOC_API_KEY` from an operating-system secret store or another protected process environment. Do not put a real key in command-line arguments, shell history, or checked-in files. Use only an endpoint you trust: sanitized error text and limited project context are sent to that service.

## Usage

```sh
errdoc <command> [arguments...]
errdoc --file error.log
some-command 2>&1 | errdoc
errdoc --no-llm <command> [arguments...]
errdoc --history <command> [arguments...]
errdoc --history-file commands.txt
errdoc --execute-fix <command> [arguments...]
fix <command> [arguments...]
```

The command is run directly as an argument vector; errdoc does not enable shell expansion or shell operators. Pipe a shell pipeline into errdoc when you need shell syntax. Command execution timeouts are limited to 600 seconds and terminate the command process tree so child processes cannot keep captured output pipes open. Captured command output keeps the newest 512 KiB per stream; `--file` retains the newest 2 MiB, and piped input retains the newest 1,000,000 characters. Each limit marks omitted earlier output. Model-generated command sections, fenced code, recognized inline commands, selected high-risk advice, and generic retry instructions tied to a hidden command are filtered from the regular CLI response while the release-quality gate is unmet. The evaluator keeps the raw answer for review, labels it untrusted, and shows the filtered user-facing text separately. Model output is never forwarded to the executor. `--execute-fix` can accept a command entered by the user, then asks for a separate yes/no confirmation before execution. Before the confirmation, errdoc writes a local JSON manifest containing the exact snapshot's included paths and sizes plus excluded paths and filter reasons; it displays the first 100 included paths and summary counts. Review the full manifest under `.errdoc` before answering yes. The confirmed run uses those exact archived bytes, so later project edits do not silently alter the reviewed snapshot. It requires a running Docker or Podman runtime plus a sandbox image already present locally and never falls back to host execution.

Each approved command runs in a disposable Linux container. errdoc sends a bounded snapshot of the current project through the container's standard input; snapshots are limited to 64 MiB of regular-file content, 10,000 files, and 20,000 filesystem entries, and commands to 16,384 characters. It does not bind-mount the project, home directory, credentials, or Docker socket. The manifest identifies included and filtered paths without copying file contents into the manifest. Symlinks, Windows reparse points, non-regular files, and unsafe archive paths are excluded or rejected. The snapshot lives on a temporary writable filesystem and is discarded after the run, so command changes do not modify the original project. The container has no network, a read-only root filesystem, an unprivileged user, dropped Linux capabilities, CPU, memory, process-count, file-size, open-file, and timeout limits. The container is forcibly removed on completion or timeout.

Snapshot selection rules:

| Snapshot item | Handling |
| --- | --- |
| Regular files in visible project directories | Included, up to the size and count limits |
| `.git`, virtual environments, `node_modules`, caches, `build`, `dist`, `.errdoc`, credentials/secrets directories | Excluded as directories |
| Hidden directories | Excluded, except `.github` |
| `.env*`, `.npmrc`, `.pypirc`, `.netrc`, SSH key filenames, and names containing secret/credential/password/token markers | Excluded by filename |
| `.pem`, `.key`, `.p12`, `.pfx`, logs, database files, dumps, and backups | Excluded by extension |
| Symlinks and Windows filesystem reparse points | Excluded; their targets are not followed |

The exact paths and reasons for the current run are in the preview manifest. A hidden file at the project root or a secret embedded in an ordinary source file may still be included. The manifest lists paths and sizes only; it does not scan file contents for secrets. Read it and review the files before confirming. The disposable snapshot is a safety layer, not a guarantee against every container-runtime vulnerability.

The default image is `python:3.11-slim`, which must already be installed locally; errdoc never downloads images automatically. Set `ERRDOC_SANDBOX_IMAGE` to another locally available image, such as a Node.js image, for projects requiring other tools. Because network access is disabled, commands cannot fetch packages during execution. Container isolation depends on the host's Docker/Podman installation and image; it is a defense layer, not a guarantee against every container-runtime vulnerability. The snapshot filter uses filenames, directories, extensions, and symlink checks; it cannot detect every secret embedded in an ordinary source file. Read the preview manifest and inspect source files for embedded credentials before approving execution. The destructive-command blacklist is an additional heuristic, not the security boundary.

## Configuration

Run `errdoc --config-init` to create `~/.errdoc/config.json`. Example:

```json
{
  "provider": "ollama",
  "model": "llama3.2",
  "base_url": "http://localhost:11434",
  "api_key": null,
  "timeout": 180,
  "max_input_chars": 12000,
  "max_output_tokens": 256
}
```

Set `provider` to `openai` to use an OpenAI-compatible API. Configure `base_url`, `model`, and `api_key` as needed. Environment variables override matching JSON keys: `ERRDOC_PROVIDER`, `ERRDOC_MODEL`, `ERRDOC_BASE_URL`, `ERRDOC_API_KEY`, `ERRDOC_TIMEOUT`, `ERRDOC_MAX_INPUT_CHARS`, and `ERRDOC_MAX_OUTPUT_TOKENS`. LLM request timeouts are limited to 600 seconds and `max_input_chars` to 1,000,000. Responses are capped at 256 tokens by default and use a low temperature for repeatability; configure `max_output_tokens` between 64 and 4096 if needed. Response bodies are limited to 1 MiB regardless of the endpoint-reported content length. `ERRDOC_CONFIG` changes the configuration file location.

When diagnosis uses an LLM, the sanitized error is sent to the configured endpoint; the sandbox project snapshot is not sent to the LLM. `detect_context()` includes only OS, OS release, Python version, and project marker names; it does not include the current directory, username, geographic location, or an IP address. Before display and before an LLM request, errdoc redacts common credential assignments (including cloud secret-key fields), credentials embedded in URLs, Basic/Bearer/Token authorization values, PEM private-key blocks, valid IPv4/IPv6 literals, the current home directory, and common Windows/macOS/Linux user-home paths. Redaction is heuristic, so review logs before sharing and do not treat this as a guarantee that every secret or identifying path is removed.

This filtering changes text sent by the application; it cannot hide the source network IP from GitHub or a remote LLM provider that receives the connection. Use local Ollama at `localhost` to keep the diagnosis request on the machine, or choose a network privacy service you trust before connecting to a remote service. Public source and release files must never contain personal logs, home paths, or IP addresses.

Generated diagnoses remain unverified. Model-generated commands and code are suppressed, and model output is never passed to the executor. Execution requires separate confirmation and only runs in the configured disposable container.

## Development

```sh
python -m pip install -e ".[test]"
python -m pytest -q -m "not integration"
```

The cross-platform unit suite excludes the integration marker, so it reports no skipped tests. Separate Linux CI jobs run the sandbox checks under Docker and Podman. To select a runtime locally, set `ERRDOC_CONTAINER_RUNTIME` to `docker` or `podman`; if unset, errdoc tries Docker and then Podman. The selected runtime must be running, and the configured sandbox image must already be available locally:

```sh
ERRDOC_RUN_SANDBOX_INTEGRATION=1 python -m pytest -m integration tests/test_executor_integration.py -q
```

To force Podman on a system that also has Docker:

```sh
ERRDOC_CONTAINER_RUNTIME=podman ERRDOC_RUN_SANDBOX_INTEGRATION=1 python -m pytest -m integration tests/test_executor_integration.py -q
```

In Windows PowerShell:

```powershell
$env:ERRDOC_RUN_SANDBOX_INTEGRATION = "1"
$env:ERRDOC_CONTAINER_RUNTIME = "docker" # or "podman"
python -m pytest -m integration tests/test_executor_integration.py -q
```

To review diagnosis correctness by hand, use the interactive evaluation command in [LLM_REVIEW_GUIDE.md](LLM_REVIEW_GUIDE.md). Human ratings are required before making reliability claims.

## Release readiness

This is an active development build, not yet a verified public release. See QUALITY_GATES.md for the release acceptance criteria and current evidence. The cross-platform CI matrix is configured but must be run on GitHub before a public release.

## Current scope

Project detection covers Django, Node.js, Git, and Python markers. Shell history is only read when the --history option is used, and any included history is processed by the log sanitizer. Suggested-command execution requires Docker/Podman and an explicit confirmation. It operates on a temporary project snapshot and does not write changes back.

## Continuous integration

The configured GitHub Actions workflow targets Windows, Linux, and macOS with Python 3.10 through 3.14. It has not yet been run on GitHub.
