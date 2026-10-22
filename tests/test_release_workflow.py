from pathlib import Path
import re


def test_github_sandbox_job_explicitly_selects_integration_tests():
    workflow = Path(__file__).parents[1] / ".github" / "workflows" / "tests.yml"
    content = workflow.read_text(encoding="utf-8")
    assert re.search(
        r"run:\s*python -m pytest -q -m integration tests/test_executor_integration\.py\b",
        content,
    )


def test_github_ci_runs_sandbox_suite_under_both_docker_and_podman():
    workflow = Path(__file__).parents[1] / ".github" / "workflows" / "tests.yml"
    content = workflow.read_text(encoding="utf-8")
    assert "podman-integration:" in content
    assert "sudo apt-get install --yes podman" in content
    assert "podman pull docker.io/library/python:3.11-slim" in content
    assert "ERRDOC_CONTAINER_RUNTIME: docker" in content
    assert "ERRDOC_CONTAINER_RUNTIME: podman" in content
    assert content.count("python -m pytest -q -m integration tests/test_executor_integration.py") == 2


def test_github_ci_matrix_covers_declared_operating_systems_and_python_versions():
    workflow = Path(__file__).parents[1] / ".github" / "workflows" / "tests.yml"
    content = workflow.read_text(encoding="utf-8")
    assert re.search(r"os:\s*\[ubuntu-latest, windows-latest, macos-latest\]", content)
    assert re.search(r'python-version:\s*\["3\.10", "3\.11", "3\.12", "3\.13", "3\.14"\]', content)
    assert "fail-fast: false" in content
    assert re.search(r"permissions:\s*\n\s+contents: read", content)


def test_github_actions_are_pinned_to_full_commit_shas():
    workflows = Path(__file__).parents[1] / ".github" / "workflows"
    content = "\n".join(path.read_text(encoding="utf-8") for path in workflows.glob("*.yml"))
    uses_refs = re.findall(r"^\s+uses:\s+[^@\s]+@([^\s#]+)", content, re.MULTILINE)
    assert uses_refs
    assert all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in uses_refs)


def test_release_workflow_only_publishes_to_testpypi_after_manual_confirmation():
    workflow = Path(__file__).parents[1] / ".github" / "workflows" / "build-release.yml"
    content = workflow.read_text(encoding="utf-8")
    build_job, publish_job = content.split("  publish-testpypi:", 1)
    assert '"v*"' in content
    assert "workflow_dispatch:" in content
    assert 'publish_to_testpypi:' in content
    assert "default: false" in content
    assert "twine check --strict" in build_job
    assert "id-token" not in build_job
    assert "pypa/gh-action-pypi-publish" not in build_job
    assert "if: github.event_name == 'workflow_dispatch' && inputs.publish_to_testpypi" in publish_job
    assert "id-token: write" in publish_job
    assert "environment:\n      name: testpypi" in publish_job
    assert "repository-url: https://test.pypi.org/legacy/" in publish_job
    assert "https://upload.pypi.org/legacy/" not in publish_job


def test_public_bug_report_template_warns_against_sensitive_data():
    template = Path(__file__).parents[1] / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml"
    content = template.read_text(encoding="utf-8").casefold()
    assert "api keys" in content
    assert "private logs" in content
    assert "security vulnerabilities" in content
    assert "public issue" in content


def test_release_metadata_uses_maintainer_identity_and_security_contact():
    root = Path(__file__).parents[1]
    project = (root / "pyproject.toml").read_text(encoding="utf-8")
    security = (root / "SECURITY.md").read_text(encoding="utf-8")
    assert project.count('name = "Mhdjamadi1994"') == 2
    assert project.count('email = "mohamadhasanjamadi1994@gmail.com"') == 2
    assert "mohamadhasanjamadi1994@gmail.com" in security


def test_github_ci_installs_built_wheel_and_source_distribution():
    workflow = Path(__file__).parents[1] / ".github" / "workflows" / "tests.yml"
    content = workflow.read_text(encoding="utf-8")
    assert "glob.glob('dist/*.whl')[0]" in content
    assert "glob.glob('dist/*.tar.gz')[0]" in content
    assert content.count("errdoc --version") == 2
    assert content.count("fix --version") == 2


def test_gitignore_excludes_common_local_secrets_and_private_artifacts():
    gitignore = Path(__file__).parents[1] / ".gitignore"
    content = gitignore.read_text(encoding="utf-8")
    for pattern in (
        ".env", ".env.*", ".npmrc", ".pypirc", ".netrc", ".aws/", ".ssh/",
        ".config/", ".kube/", ".azure/", ".gcloud/", "*.pem", "*.key", "*.log", "*.sqlite3",
    ):
        assert pattern in content
    assert "!.env.example" in content


def test_source_distribution_manifest_includes_runtime_audit_lock():
    manifest = Path(__file__).parents[1] / "MANIFEST.in"
    assert "include requirements-audit.txt" in manifest.read_text(encoding="utf-8")


def test_dependabot_updates_python_and_github_actions_weekly():
    dependabot = Path(__file__).parents[1] / ".github" / "dependabot.yml"
    content = dependabot.read_text(encoding="utf-8")
    assert content.count("package-ecosystem: pip") == 1
    assert content.count("package-ecosystem: github-actions") == 1
    assert content.count("interval: weekly") == 2


def test_github_ci_audits_locked_runtime_dependencies():
    workflow = Path(__file__).parents[1] / ".github" / "workflows" / "tests.yml"
    content = workflow.read_text(encoding="utf-8")
    assert "dependency-audit:" in content
    assert "python -m pip install --target /tmp/errdoc-runtime --requirement requirements-audit.txt" in content
    assert "python -m pip_audit --path /tmp/errdoc-runtime --progress-spinner off" in content

    lock = Path(__file__).parents[1] / "requirements-audit.txt"
    requirements = [line.strip() for line in lock.read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")]
    assert {line.split("==", 1)[0].lower().replace("_", "-") for line in requirements} == {
        "click", "rich", "markdown-it-py", "pygments", "mdurl"
    }
    assert all(re.fullmatch(r"[A-Za-z0-9_.-]+==[^;\s]+", line) for line in requirements)
