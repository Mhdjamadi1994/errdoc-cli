# errdoc

**Turn failed commands into clearer next steps.**

errdoc runs a command you choose, captures its error output, and explains the likely cause in plain language. Use built-in rules or connect a local Ollama model or an OpenAI-compatible service. errdoc never executes commands suggested by a model.

<p>
  <a href="#quick-start">🚀 Quick start</a> ·
  <a href="#choose-a-tool">🧰 Choose a tool</a> ·
  <a href="#privacy-in-plain-words">🔒 Privacy</a> ·
  <a href="#safe-fix-preview">📦 Safe fix preview</a> ·
  <a href="#help-and-project-status">❓ Help and status</a>
</p>

[![CI](https://github.com/Mhdjamadi1994/errdoc-cli/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/Mhdjamadi1994/errdoc-cli/actions/workflows/tests.yml) · Python 3.10+ · [MIT license](LICENSE) · [Private vulnerability reporting](SECURITY.md)

> **Project status: pre-release.** The source code is public on GitHub, but the package has not been published to PyPI. AI explanations can be wrong. Read the privacy and safety notes below before using real logs or the optional fix runner.

## How it works

1. You choose a command to run or a log to inspect.
2. errdoc trims long output and tries to hide common secrets and personal paths.
3. It uses local rules or sends the sanitized error to the model provider you configured.
4. It prints an explanation. You decide what to do next.

errdoc does not send your project snapshot to the diagnosis model. Model suggestions are untrusted and are never sent to the command runner.

## Quick start

errdoc currently installs from this GitHub repository. **`pip install errdoc-cli` will not work yet** because the package is not on PyPI.

You need Python 3.10 or newer. In a terminal:

```sh
git clone https://github.com/Mhdjamadi1994/errdoc-cli.git
cd errdoc-cli
python -m venv .venv
```

Activate the environment and install errdoc:

**Windows PowerShell**

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

**macOS or Linux**

```sh
source .venv/bin/activate
python -m pip install -e .
```

For AI explanations, install and start [Ollama](https://ollama.com/), then download the default model:

```sh
ollama pull llama3.2
```

Try errdoc:

```sh
errdoc python -c "import missing_module"
```

The command should fail on purpose. errdoc then explains the error. The first Ollama request can take longer while the model starts.

## Choose a tool

Use the link for the task you have. Each option has its own example and explanation.

| I want to… | Use this | Guide |
| --- | --- | --- |
| Explain a command that failed | `errdoc <command> [arguments]` | [Run a command](#run-a-command) |
| Explain a saved log | `errdoc --file error.log` | [Read a log file](#read-a-log-file) |
| Explain output from another command | Connect its output to errdoc | [Use a pipe](#use-a-pipe) |
| Avoid contacting an AI model | `errdoc --no-llm <command>` | [Use offline rules](#use-offline-rules) |
| Include selected shell history | `--history` or `--history-file` | [Include shell history](#include-shell-history) |
| Try a command in an isolated copy | `errdoc --execute-fix <command>` or `fix <command>` | [Review a fix preview](#safe-fix-preview) |
| Create or change settings | `errdoc --config-init` or `~/.errdoc/config.json` | [Set up a model](#set-up-a-model) |

### Run a command

```sh
errdoc python -m pytest
```

errdoc runs the command you provide and explains its output if it fails. It does not interpret shell operators inside the command. If you need pipes, use your shell to connect the output to errdoc; see [Use a pipe](#use-a-pipe).

Use `--timeout SECONDS` before the command to change the wait limit. The default is 120 seconds; the maximum is 600 seconds.

### Read a log file

```sh
errdoc --file error.log
```

The newest 2 MiB of the file are kept. Earlier text is left out and marked as omitted.

### Use a pipe

```sh
python -m pytest 2>&1 | errdoc
```

The newest 1,000,000 characters are kept. Review a log before sending it to a remote model; automatic secret hiding is not perfect.

### Use offline rules

```sh
errdoc --no-llm python -m pytest
```

This uses errdoc's built-in rules and does not contact a model service. It only recognizes selected errors, so it may not explain every failure.

### Include shell history

History is optional. Add `--history` to include recent history, or `--history-file PATH` to choose a history file. Review it first: history can contain private commands, paths, or tokens. It passes through the same best-effort sanitizer as other text.

## Set up a model

### Use Ollama on your computer

Install Ollama using its [official instructions](https://ollama.com/download), start it, and download a model such as `llama3.2`:

```sh
ollama pull llama3.2
```

By default, errdoc connects to Ollama at `http://localhost:11434`. The model runs on your computer. Downloading the model is a separate step; errdoc does not download it for you.

### Use an OpenAI-compatible service

Set `provider`, `base_url`, and `model` in `~/.errdoc/config.json`, or use the matching `ERRDOC_*` environment variables. Put your API key in a protected environment variable such as `ERRDOC_API_KEY`; do not put it in a command, shell history, or a file you commit.

When you use a remote service, errdoc sends sanitized error text and limited system context to that service. Check that provider's privacy terms before connecting.

### Change settings

Run `errdoc --config-init` to create the starter configuration file. Environment variables override values in that file. Supported settings and limits are listed in [Configuration details](#configuration-details).

#### Configuration details

| Setting | Default | What it controls |
| --- | --- | --- |
| `ERRDOC_PROVIDER` | `ollama` | `ollama` or `openai` |
| `ERRDOC_MODEL` | `llama3.2` | Model name used by the provider |
| `ERRDOC_BASE_URL` | `http://localhost:11434` | Provider address |
| `ERRDOC_API_KEY` | none | API key for a remote provider |
| `ERRDOC_TIMEOUT` | `180` | Model request timeout in seconds |
| `ERRDOC_MAX_INPUT_CHARS` | `12000` | Maximum text sent to the model (up to 1,000,000) |
| `ERRDOC_MAX_OUTPUT_TOKENS` | `256` | Maximum response size (64–4096) |
| `ERRDOC_CONFIG` | `~/.errdoc/config.json` | Alternate settings-file location |

## Privacy in plain words

- For an AI explanation, errdoc sends the error text and a small amount of context to the provider you selected.
- Local Ollama keeps that request on your computer. A remote provider receives it over the network.
- The project files prepared for the optional fix runner are **not** sent to the diagnosis model.
- errdoc tries to hide common passwords, API keys, IP addresses, and personal home-folder paths. This is a best-effort filter, not a guarantee. A secret inside a normal source file or an unfamiliar format may not be found.
- Review logs and history before sending them, especially to a remote provider.
- A remote provider can see the connection's source IP. Redacting text does not hide network information.

See [SECURITY.md](SECURITY.md) for private vulnerability reporting.

## Safe fix preview

The optional fix runner is for a command **you type yourself**. It does not run commands suggested by a model.

```sh
errdoc --execute-fix <command> [arguments...]
```

or:

```sh
fix <command> [arguments...]
```

Before asking for your confirmation, errdoc creates a preview manifest with the paths and sizes it plans to include and the reasons other paths are excluded. It displays the first 100 included paths and summary counts. Open the full manifest under `.errdoc` and inspect the listed files before answering yes. The run uses those exact previewed bytes.

### What goes into the temporary copy

| Usually included | Excluded or rejected |
| --- | --- |
| Regular files in visible project folders | `.git`, virtual environments, caches, build outputs, `dist`, and `.errdoc` |
| `.github` files | Other hidden folders |
| Files that fit the snapshot size and count limits | `.env*`, credential-named files, key files, logs, databases, dumps, backups |
|  | Symlinks, Windows reparse points, special files, unsafe archive paths |

The snapshot is limited to 64 MiB of file contents, 10,000 files, and 20,000 filesystem entries. The manifest lists names and sizes, not file contents. The filter does not inspect ordinary source files for secrets; a hidden file at the project root or a credential inside a regular source file may still be copied. Check the preview and inspect your files before confirming.

### Where the command runs

After confirmation, the command runs in a temporary Linux container using Docker or Podman. The container has no network, uses a read-only root and an unprivileged user, and is removed when the run ends. The project is copied into a temporary filesystem; it is not mounted back over your original project, so changes inside the container are discarded.

You must already have a working Docker or Podman runtime and a local image. The default image is `python:3.11-slim`; errdoc does not download images automatically and does not fall back to running the command on your computer. Container isolation lowers risk, but cannot guarantee protection from every host or container-runtime vulnerability.

## Common problems

| Problem | What to check |
| --- | --- |
| Ollama connection fails | Start Ollama and confirm the model is downloaded with `ollama list`. |
| Remote model request fails | Check the provider URL, model name, API key, network, and timeout. |
| `--execute-fix` cannot start | Start Docker or Podman and confirm the configured image exists locally. |
| The explanation is wrong or vague | Treat it as a suggestion. Compare it with the original error and consult the tool's documentation. |
| A fix command changes files | Changes happen in the temporary copy and are discarded; apply any useful change yourself after reviewing it. |

## Help and project status

errdoc is an early pre-release project, not a debugger. Its explanations are suggestions to check against the original error and the tool's documentation.

### Current evaluation

On October 22, 2026, the owner reviewed 51 answers from the updated `llama3.2` evaluation. The mean score across accuracy, specificity, safety, and concision was **9.29/10**. The separate correctness labels were **0 correct, 51 partially correct, 0 incorrect, and 0 unsafe**. No answer was labeled fully correct, so the 90% correctness gate is **not met**. The 9.29 average is not an accuracy rate. Automatic checks also found no unsafe or command suggestions, generic-advice flags, unsupported-claim flags, or overlong answers; those checks do not replace human correctness review.

See the [score-only results for this version](docs/llm-human-review-post-diagnostics-v2-2026-10-22.csv), the [older baseline results](docs/llm-human-review-2026-10-22.csv), the [trust assessment](docs/trust-assessment-2026-10-22.md), [review instructions](LLM_REVIEW_GUIDE.md), and [release gates](QUALITY_GATES.md).

The package is not yet published to PyPI. TestPyPI publishing, project-name ownership, and remaining privacy/release checks still need verification.

- [**Review the tests and release gates →**](QUALITY_GATES.md)
- [**Report a security issue privately →**](SECURITY.md)
- [**Contribute or run tests →**](CONTRIBUTING.md)
- [**Review the model answers by hand →**](LLM_REVIEW_GUIDE.md)
- [**See project changes →**](CHANGELOG.md)
- [**Open a bug report →**](https://github.com/Mhdjamadi1994/errdoc-cli/issues/new/choose)

If errdoc helps you, consider starring the repository. Stars are optional and do not replace bug reports or independent review.

## Run tests

From the repository folder:

```sh
python -m pip install -e ".[test]"
python -m pytest -q -m "not integration"
```

The separate container tests require a running Docker or Podman installation and a local sandbox image:

```sh
ERRDOC_RUN_SANDBOX_INTEGRATION=1 python -m pytest -m integration tests/test_executor_integration.py -q
```

The hosted workflow checks Windows, Linux, and macOS with Python 3.10 through 3.14. Its live result is shown by the CI badge at the top of this page.
