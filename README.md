# errdoc

**Turn a failed command into a useful next step—without handing your project to a model or running AI-generated fixes.** `errdoc` is a cross-platform CLI for developers who want a concise, evidence-based explanation of build, test, deployment, and runtime errors. It captures the failure, trims noisy output, redacts common secrets and identifying paths, then asks a local Ollama model or an OpenAI-compatible endpoint to explain it.

```sh
errdoc python -c "import missing_module"
```

`errdoc` keeps command execution, diagnosis, and optional fixes separate: generated advice is untrusted and is never sent to the executor. If you explicitly choose `--execute-fix`, you review the exact project snapshot before confirming; the command runs in a disposable, network-disabled Docker or Podman container. You can also use `--no-llm` for local deterministic analysis.

**Designed for:** developers debugging unfamiliar tracebacks, CI failures, dependency errors, and deployment logs who want a quick explanation while keeping control of their data and changes.

The PyPI distribution is named `errdoc-cli`; it installs the `errdoc` command and the shorter `fix` alias. The package has not been published yet.

## On this page

- [Install and choose a diagnosis provider](#install)
- [Tools and capabilities](#tools-and-capabilities)
- [Sandboxed fix execution](#sandboxed-fix-execution)
- [Configuration](#configuration)
- [Privacy and data flow](#privacy-and-data-flow)
- [Development and tests](#development)
- [Release readiness](#release-readiness)

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

## Tools and capabilities

| Tool or option | What it does | Details |
| --- | --- | --- |
| `errdoc <command> [arguments...]` | Runs a command and explains its failure | [Command analysis](#command-analysis) |
| `errdoc --file error.log` | Analyzes an existing log file | [Log and pipe input](#log-and-pipe-input) |
| `errdoc --no-llm <command> [arguments...]` | Uses local diagnosis rules without a model | [Offline diagnosis](#offline-diagnosis) |
| Ollama or an OpenAI-compatible endpoint | Generates a concise diagnosis from sanitized error text | [Model diagnosis](#model-diagnosis) |
| `--history`, `--history-file` | Adds selected shell history to diagnosis | [History input](#history-input) |
| `--execute-fix` or `fix <command> [arguments...]` | Runs a user-entered command after preview and confirmation | [Sandboxed fix execution](#sandboxed-fix-execution) |
| `errdoc --config-init` | Creates the user configuration file | [Configuration](#configuration) |

### Command analysis

```sh
errdoc python -c "import missing_module"
```

errdoc starts the command directly as an argument vector. It does not enable shell expansion, pipes, redirects, or shell operators inside that command. Use a shell pipeline piped into errdoc when you need shell syntax. Command timeouts are capped at 600 seconds, and errdoc terminates the command process tree so child processes cannot keep output pipes open. Captured output retains the newest 512 KiB per stream and marks omitted earlier output.

### Log and pipe input

```sh
errdoc --file error.log
some-command 2>&1 | errdoc
```

File input retains the newest 2 MiB; piped input retains the newest 1,000,000 characters. Each input limit marks omitted earlier content. Review and redact logs before sharing them with a remote model provider; see [Privacy and data flow](#privacy-and-data-flow).

### Offline diagnosis

```sh
errdoc --no-llm python -c "import missing_module"
```

This option uses errdoc's local diagnosis rules and does not contact an LLM endpoint. It is useful for predictable, common errors or environments where model access is unavailable. The rule set covers selected error patterns; it does not replace a full debugger or guarantee a diagnosis for every failure.

### Model diagnosis

errdoc can send sanitized error text and limited context to local Ollama or a configured OpenAI-compatible endpoint. The project snapshot used for sandboxed fixes is not sent to the diagnosis model. See [Local Ollama](#local-ollama), [OpenAI-compatible endpoint](#openai-compatible-endpoint), [Configuration](#configuration), and [Privacy and data flow](#privacy-and-data-flow) for setup and limits.

### History input

Use `--history` to include the selected shell history for a command, or `--history-file` to analyze a chosen history file. History is opt-in and passes through the same log sanitizer. Review the resulting input for sensitive values; redaction is heuristic.

## Sandboxed fix execution

```sh
errdoc --execute-fix <command> [arguments...]
fix <command> [arguments...]
```

The proposed command must be entered by the user. errdoc then creates a local JSON preview manifest listing included paths and sizes and excluded paths with filter reasons, and asks for a separate yes/no confirmation. It shows the first 100 included paths and summary counts; inspect the full manifest under `.errdoc` and review the project files before approving. The run uses the exact archived bytes shown in that preview, so later edits do not silently change the reviewed snapshot. Model output is never forwarded to the executor.

After confirmation, errdoc runs the command in a disposable Linux Docker or Podman container. It never falls back to host execution. The default image is `python:3.11-slim` and must already exist locally; errdoc does not download images. Set `ERRDOC_SANDBOX_IMAGE` to another local image, such as a Node.js image, when required. Network access is disabled, so the command cannot download packages during execution.

Snapshot limits are 64 MiB of regular-file content, 10,000 files, 20,000 filesystem entries, and 16,384 command characters. errdoc does not bind-mount the project, home directory, credentials, or Docker socket. The snapshot is passed through standard input to a temporary writable filesystem and discarded afterward. The container also uses a read-only root, an unprivileged user, dropped Linux capabilities, and CPU, memory, process, file-size, open-file, and time limits. errdoc removes the container on completion or timeout.

### Snapshot preview and exclusions

| Snapshot item | Handling |
| --- | --- |
| Regular files in visible project directories | Included, within the size and count limits |
| `.git`, virtual environments, `node_modules`, caches, `build`, `dist`, `.errdoc`, credential and secret directories | Excluded as directories |
| Hidden directories | Excluded, except `.github` |
| `.env*`, `.npmrc`, `.pypirc`, `.netrc`, SSH key names, and names containing secret/credential/password/token markers | Excluded by filename |
| `.pem`, `.key`, `.p12`, `.pfx`, logs, database files, dumps, and backups | Excluded by extension |
| Symlinks and Windows filesystem reparse points | Excluded; targets are not followed |
| Non-regular files and unsafe archive paths | Excluded or rejected |

The manifest records paths, sizes, and exclusion reasons, not file contents. A hidden file at the project root or a secret embedded in an ordinary source file may still be included. The filter checks names, directories, extensions, and links; it does not scan file contents for secrets. Inspect source files and the manifest before confirming. The destructive-command blacklist is an additional heuristic, not the security boundary. Container isolation depends on the host runtime and image; it reduces risk but cannot guarantee protection from every runtime vulnerability.

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

## Privacy and data flow

When diagnosis uses an LLM, errdoc sends the sanitized error and limited context to the configured endpoint; it does not send the sandbox project snapshot. `detect_context()` includes only the operating system, OS release, Python version, and project marker names. It does not include the current directory, username, geographic location, or IP address.

Before display and before an LLM request, errdoc redacts common credential assignments (including cloud secret-key fields), credentials in URLs, Basic/Bearer/Token authorization values, PEM private-key blocks, valid IPv4/IPv6 literals, the current home directory, and common Windows/macOS/Linux user-home paths. A four-part number explicitly labeled `Version=` is preserved so assembly version metadata remains useful. Redaction is heuristic: inspect logs before sharing and do not assume every secret or identifying path will be removed.

Redaction changes the text errdoc sends; it cannot hide the source network IP from GitHub or a remote model provider that receives the connection. Use local Ollama at `localhost` to keep diagnosis requests on the machine, or choose a remote service you trust. Generated diagnoses remain unverified. Model-generated commands and code are suppressed, and model output is never sent to the executor. Fix execution always requires separate confirmation and runs only in the disposable container described in [Sandboxed fix execution](#sandboxed-fix-execution).

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

This is an active pre-release build; the PyPI package is not published. Commit `1f25922` passed all 18 GitHub Actions checks on October 22, 2026, including the platform/Python matrix, Docker, Podman, and dependency audit. See [QUALITY_GATES.md](QUALITY_GATES.md) for release criteria, evidence, and remaining work. Passing CI does not by itself establish diagnosis accuracy or complete release readiness.

## Current scope

Project detection covers Django, Node.js, Git, and Python markers. Shell history is only read when the --history option is used, and any included history is processed by the log sanitizer. Suggested-command execution requires Docker/Podman and an explicit confirmation. It operates on a temporary project snapshot and does not write changes back.

## Continuous integration

The configured GitHub Actions workflow tests Windows, Linux, and macOS on Python 3.10 through 3.14, builds and installs both wheel and source distributions, and runs Linux Docker/Podman sandbox checks. Run 39773246844 for commit `1f25922` passed all 18 checks on October 22, 2026. See the [Actions history](https://github.com/Mhdjamadi1994/errdoc-cli/actions/workflows/tests.yml) for live status.
