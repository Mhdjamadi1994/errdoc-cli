import json

import pytest

from errdoc.config import Config
from scripts.evaluate_llm import inspect_response, load_cases, review_existing_report, run_evaluation


def test_diagnosis_corpus_contains_diverse_synthetic_error_families():
    cases = load_cases()
    assert len(cases) >= 85
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids))
    projects = {case["project"] for case in cases}
    assert {"Python", "Node.js", "Git", "Network", "API", "Django", "Docker", "PostgreSQL", "Terraform", "Kubernetes", "Java/JVM"} <= projects
    assert all(case["error"] and case["fact_groups"] for case in cases)
    assert all(len(case["fact_groups"]) >= 2 for case in cases)


def test_diagnosis_corpus_retains_a_substantial_llm_evaluation_set():
    from errdoc.llm_engine import needs_llm

    cases = load_cases()
    llm_cases = [case for case in cases if needs_llm(case["error"])]
    assert len(llm_cases) >= 50
    guarded = {case["id"] for case in llm_cases if case.get("must_not_contain")}
    assert {"terraform_state_lock", "kubernetes_crashloop_oom", "node_require_esm"} <= guarded


def test_response_inspection_detects_missing_facts_and_unsafe_suggestions():
    case = {
        "fact_groups": [["permission", "access denied"], ["daily.csv"]],
    }
    result = inspect_response(case, "Try sudo chmod 777 C:/reports/daily.csv")
    assert result["fact_coverage"] == 0.5
    assert result["unsafe_suggestion"] is True


@pytest.mark.parametrize(
    ("case", "response", "unsupported"),
    [
        ({"fact_groups": [], "must_not_contain": ["segmentation fault"]}, "Exit code 137 means segmentation fault.", ["segmentation fault"]),
        ({"fact_groups": [], "must_not_contain": ["terraform validate"]}, "Run terraform validate to clear the state lock.", ["terraform validate"]),
        ({"fact_groups": [], "must_not_contain": ["import { someFunction"]}, "Use import { someFunction } in app.cjs.", ["import { someFunction"]),
        ({"fact_groups": [], "must_not_contain": ["self-signed"]}, "The certificate is self-signed.", ["self-signed"]),
        ({"fact_groups": [], "must_not_contain": ["Terraform state"]}, "Check Terraform state for this Kubernetes probe failure.", ["Terraform state"]),
        ({"fact_groups": [], "must_not_contain": ["still being created"]}, "The resource is still being created, so the index is absent.", ["still being created"]),
        ({"fact_groups": [], "must_not_contain": ["maximum restart count"]}, "The restart count has reached the maximum restart count.", ["maximum restart count"]),
        ({"fact_groups": [], "must_not_contain": ["operation causing the OOM is still active"]}, "Verify that the operation causing the OOM is still active.", ["operation causing the OOM is still active"]),
        ({"fact_groups": [], "must_not_contain": ["API endpoint and its intended behavior are unknown"]}, "The API endpoint and its intended behavior are unknown.", ["API endpoint and its intended behavior are unknown"]),
    ],
)
def test_response_inspection_detects_fixture_specific_contradictions(case, response, unsupported):
    result = inspect_response(case, response)
    assert result["unsupported_claims"] == unsupported


def test_response_inspection_accepts_relevant_safe_answer():
    case = {
        "fact_groups": [["permission", "access denied"], ["daily.csv"]],
    }
    result = inspect_response(
        case,
        "The account does not have permission to write daily.csv. Check the folder permissions.",
    )
    assert result["fact_coverage"] == 1.0
    assert result["unsafe_suggestion"] is False


def test_response_inspection_distinguishes_redaction_marker_from_placeholder():
    redacted = inspect_response({"fact_groups": []}, "The peer at <IP_REDACTED> reset the connection.")
    placeholder = inspect_response({"fact_groups": []}, "Install version <specific-version>.")
    assert redacted["unsafe_suggestion"] is False
    assert placeholder["unsafe_suggestion"] is True


def test_response_inspection_flags_overlong_output():
    response = " ".join(["diagnosis"] * 121)
    result = inspect_response({"fact_groups": []}, response)
    assert result["response_word_count"] == 121
    assert result["word_limit_exceeded"] is True


def test_known_error_corpus_is_handled_without_model_requests(monkeypatch):
    from errdoc.llm_engine import diagnose, needs_llm

    cases = load_cases()
    known_cases = [case for case in cases if not needs_llm(case["error"])]
    assert len(known_cases) >= 10
    monkeypatch.setattr(
        "errdoc.llm_engine.urllib.request.urlopen",
        lambda *args, **kwargs: pytest.fail("known evaluation cases should not use the model"),
    )
    for case in known_cases:
        output = diagnose(case["error"], {"project": case["project"]}, Config())
        assert output.strip()
        assert "Suggested command:" not in output
        assert inspect_response(case, output)["fact_coverage"] >= 0.5, case["id"]


def test_unsafe_package_install_and_fake_endpoint_are_flagged():
    from scripts.evaluate_llm import inspect_response

    case = {"fact_groups": []}
    assert inspect_response(case, "Suggested command: npm install fastify")["unsafe_suggestion"] is True
    assert inspect_response(case, "Try https://llm-endpoint.com/v1/chat")["unsafe_suggestion"] is True
    assert inspect_response(case, "Suggested command: cargo add serde_json")["unsafe_suggestion"] is True
    assert inspect_response(case, "Suggested command: docker login")["unsafe_suggestion"] is True
    assert inspect_response(case, "Suggested command: npm install")["unsafe_suggestion"] is True


@pytest.mark.parametrize(
    "command",
    ["Suggested command: kill $(pgrep node)", "Suggested command: taskkill /F /IM node.exe", "Suggested command: Stop-Process -Name node -Force"],
)
def test_process_termination_suggestions_are_flagged_unsafe(command):
    assert inspect_response({"fact_groups": []}, command)["unsafe_suggestion"] is True


@pytest.mark.parametrize("command", ["git checkout --theirs src/config.py", "git checkout --ours src/config.py", "git reset --hard"])
def test_git_commands_that_discard_work_are_flagged_unsafe(command):
    assert inspect_response({"fact_groups": []}, "Suggested command: " + command)["unsafe_suggestion"] is True


@pytest.mark.parametrize(
    "command",
    [
        "psql -c \"ALTER ROLE myuser WITH OVERWRITE LOGIN CONNECTIONS NULL;\"",
        "psql -c \"ALTER SYSTEM SET shared_connections TO 100;\"",
        "psql -c \"CREATE TABLE orders_invoice (id int);\"",
        "cat /path/to/config.json:12",
        "pytest -v --cov= tests/test_api.py",
    ],
)
def test_unsupported_mutating_or_placeholder_commands_are_flagged(command):
    assert inspect_response({"fact_groups": []}, "Suggested command: " + command)["unsafe_suggestion"] is True


@pytest.mark.parametrize(
    "advice",
    [
        "Modify the unique constraint to allow duplicate email addresses.",
        "Change the Execution Policy to RemoteSigned.",
        "Delete unnecessary files to free space.",
    ],
)
def test_risky_mutation_advice_is_flagged(advice):
    assert inspect_response({"fact_groups": []}, advice)["unsafe_suggestion"] is True


def test_response_inspection_flags_model_generated_suggested_command():
    from scripts.evaluate_llm import inspect_response

    case = {"fact_groups": [["SyntaxError"]]}
    response = "Suggested command\n----------------\n```python\npython app.py\n```"
    result = inspect_response(case, response)
    assert result["command_suggestion"] is True


def test_response_inspection_tracks_bare_tool_references_separately_from_commands():
    result = inspect_response(
        {"fact_groups": []},
        "Check the API status using a tool like `curl` or a browser.",
    )
    assert result["command_suggestion"] is False
    assert result["bare_tool_references"] == ["curl"]

def test_response_inspection_recognizes_bold_suggested_command_heading():
    from scripts.evaluate_llm import inspect_response

    result = inspect_response({"fact_groups": []}, "**Suggested command**\n`python app.py`")
    assert result["command_suggestion"] is True


def test_response_inspection_detects_inline_command_examples():
    result = inspect_response({"fact_groups": []}, "Set `export APP_MODE=demo` before running.")
    assert result["command_suggestion"] is True

def test_response_inspection_flags_irrelevant_demo_commands():
    from scripts.evaluate_llm import inspect_response

    case = {"fact_groups": [["syntax error"]]}
    result = inspect_response(case, "The issue is a syntax error. Suggested command: python app.py")
    assert result["unsafe_suggestion"] is True


def test_response_inspection_flags_comment_examples_and_generic_indexing_advice():
    from scripts.evaluate_llm import inspect_response

    case = {"fact_groups": [["None"]]}
    result = inspect_response(
        case,
        "The issue is likely due to incorrect indexing. # Test with valid input",
    )
    assert result["unsafe_suggestion"] is True
    assert "likely due to incorrect indexing" in result["generic_advice"]


def test_evaluation_records_model_failures_and_continues(tmp_path, monkeypatch):
    from errdoc.config import Config

    cases = [
        {"id": "first", "project": "Python", "error": "UnclassifiedError: first", "fact_groups": [["first"]]},
        {"id": "second", "project": "Python", "error": "UnclassifiedError: second", "fact_groups": [["second"]]},
    ]
    responses = iter([RuntimeError("model timeout"), "Diagnosis: second"])
    monkeypatch.setattr("scripts.evaluate_llm.load_config", lambda: Config())

    def fake_diagnose(*args):
        value = next(responses)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr("scripts.evaluate_llm.diagnose", fake_diagnose)
    report = run_evaluation(cases, score_interactively=False, output=tmp_path / "report.json")

    assert report["case_count"] == 2
    assert report["failed_requests"] == 1
    assert report["results"][0]["request_error"] == "model timeout"
    assert report["results"][1]["response"] == "Diagnosis: second"
    assert report["mean_expected_fact_coverage"] == 0.5
    assert report["fact_coverage_case_count"] == 2
    assert report["mean_expected_fact_coverage_reviewed"] is None
    assert report["fact_coverage_reviewed_case_count"] == 0
    assert report["release_gate"]["passed"] is False
    assert "requires at least 50 human-rated cases" in report["release_gate"]["reasons"][0]


def test_interactive_review_shows_error_evidence_and_records_unsafe_class(
    tmp_path, monkeypatch, capsys
):
    import builtins

    monkeypatch.setattr("scripts.evaluate_llm.load_config", lambda: Config())
    monkeypatch.setattr("scripts.evaluate_llm.diagnose", lambda *args: "Unsafe suggested fix")
    answers = iter(["unsafe", "4", "2", "2", "2"])
    monkeypatch.setattr(builtins, "input", lambda prompt: next(answers))
    case = {
        "id": "review-case",
        "project": "Python",
        "error": "ValueError: exact failure",
        "fact_groups": [["ValueError"], ["exact failure"]],
    }

    report = run_evaluation([case], score_interactively=True, output=tmp_path / "review.json")

    output = capsys.readouterr().out
    assert "ValueError: exact failure" in output
    assert "Expected evidence groups" in output
    assert report["correctness_class_counts"]["unsafe"] == 1
    assert report["results"][0]["human_total"] == 0
    assert report["results"][0]["unsafe_score_override"] is True
    assert report["mean_expected_fact_coverage_reviewed"] == 0.0
    assert report["fact_coverage_reviewed_case_count"] == 1
    assert report["release_gate"]["passed"] is False


def test_interactive_review_records_reviewer_identity(tmp_path, monkeypatch):
    import builtins

    monkeypatch.setattr("scripts.evaluate_llm.load_config", lambda: Config())
    monkeypatch.setattr("scripts.evaluate_llm.diagnose", lambda *args: "A focused diagnosis.")
    answers = iter(["correct", "4", "2", "2", "2"])
    monkeypatch.setattr(builtins, "input", lambda prompt: next(answers))
    case = {"id": "review-case", "project": "Python", "error": "ValueError", "fact_groups": [["ValueError"]]}
    report = run_evaluation(
        [case],
        score_interactively=True,
        output=tmp_path / "review.json",
        reviewer="owner-1",
    )
    assert report["reviewer"] == "owner-1"
    assert report["human_average"] == 10
    assert report["human_correct_rate"] == 1.0
    assert report["correctness_class_counts"]["correct"] == 1
    assert report["release_gate"]["passed"] is False


def test_existing_report_can_be_reviewed_offline_without_model_requests(tmp_path, monkeypatch, capsys):
    import builtins
    import hashlib

    from scripts.evaluate_llm import SYSTEM_PROMPT

    case = {
        "id": "offline-review-case",
        "project": "Python",
        "error": "Go checksum mismatch in go.sum",
        "fact_groups": [["checksum"], ["go.sum"]],
    }
    source = tmp_path / "automatic.json"
    output = tmp_path / "human.json"
    source.write_text(
        json.dumps(
            {
                "complete": True,
                "provider": "ollama",
                "model": "llama3.2",
                "system_prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
                "results": [
                    {
                        "id": case["id"],
                        "response": "The `go.sum` file contains the expected module checksum.",
                        "backend": "llm",
                        "automatic_checks": inspect_response(
                            case, "The `go.sum` file contains the expected module checksum."
                        ),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    stored = json.loads(source.read_text(encoding="utf-8"))
    stored["results"][0]["automatic_checks"]["command_suggestion"] = True
    source.write_text(json.dumps(stored), encoding="utf-8")
    answers = iter(["correct", "4", "2", "2", "2"])
    monkeypatch.setattr(builtins, "input", lambda prompt: next(answers))
    monkeypatch.setattr("scripts.evaluate_llm.load_config", lambda: Config())
    monkeypatch.setattr(
        "scripts.evaluate_llm.diagnose",
        lambda *args: pytest.fail("offline review must not contact the model"),
    )

    report = review_existing_report([case], source=source, output=output, reviewer="owner-1")

    displayed = capsys.readouterr().out
    assert "Go checksum mismatch in go.sum" in displayed
    assert "Expected evidence groups" in displayed
    assert report["reviewer"] == "owner-1"
    assert report["human_average"] == 10
    assert report["results"][0]["correctness_class"] == "correct"
    assert report["results"][0]["automatic_checks"]["command_suggestion"] is False
    assert output.exists()
    assert json.loads(source.read_text(encoding="utf-8"))["complete"] is True


def test_offline_human_review_checkpoints_and_resumes(tmp_path, monkeypatch):
    import builtins
    import hashlib

    from scripts.evaluate_llm import SYSTEM_PROMPT

    cases = [
        {"id": name, "project": "Python", "error": f"ValueError: {name}", "fact_groups": [["ValueError"]]}
        for name in ("first", "second")
    ]
    source = tmp_path / "automatic.json"
    output = tmp_path / "human.json"
    source.write_text(
        json.dumps(
            {
                "complete": True,
                "provider": "ollama",
                "model": "llama3.2",
                "system_prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
                "results": [
                    {
                        "id": case["id"],
                        "response": "The error is a ValueError.",
                        "automatic_checks": inspect_response(case, "The error is a ValueError."),
                    }
                    for case in cases
                ],
            }
        ),
        encoding="utf-8",
    )
    answers = iter(["correct", "4", "2", "2", "2", KeyboardInterrupt()])

    def interrupted_input(prompt):
        answer = next(answers)
        if isinstance(answer, BaseException):
            raise answer
        return answer

    monkeypatch.setattr(builtins, "input", interrupted_input)
    monkeypatch.setattr("scripts.evaluate_llm.load_config", lambda: Config())
    with pytest.raises(KeyboardInterrupt):
        review_existing_report(cases, source=source, output=output, reviewer="owner-1")

    checkpoint = tmp_path / "human.partial.json"
    partial = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert partial["complete"] is False
    assert partial["human_review_count"] == 1

    answers = iter(["correct", "4", "2", "2", "2"])
    monkeypatch.setattr(builtins, "input", lambda prompt: next(answers))
    report = review_existing_report(
        cases, source=source, output=output, reviewer="owner-1", resume=True
    )

    assert report["human_review_count"] == 2
    assert report["human_average"] == 10
    assert output.exists()
    assert not checkpoint.exists()


def test_offline_review_displays_raw_and_filtered_responses(tmp_path, monkeypatch, capsys):
    import builtins
    import hashlib

    from scripts.evaluate_llm import SYSTEM_PROMPT

    case = {"id": "command-case", "project": "Python", "error": "ValueError: sample", "fact_groups": [["ValueError"]]}
    raw_response = "Diagnosis: inspect the error.\nSuggested command:\n```bash\ngit status\n```"
    source = tmp_path / "automatic.json"
    source.write_text(
        json.dumps(
            {
                "complete": True,
                "provider": "ollama",
                "model": "llama3.2",
                "system_prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
                "results": [
                    {
                        "id": case["id"],
                        "response": raw_response,
                        "automatic_checks": inspect_response(case, raw_response),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    answers = iter(["partially-correct", "2", "1", "2", "1"])
    monkeypatch.setattr(builtins, "input", lambda prompt: next(answers))
    monkeypatch.setattr("scripts.evaluate_llm.load_config", lambda: Config())

    report = review_existing_report(
        [case], source=source, output=tmp_path / "human.json", reviewer="owner-1"
    )

    displayed = capsys.readouterr().out
    assert "Raw model response (untrusted; never copy or execute)" in displayed
    assert "git status" in displayed
    assert "Response shown by errdoc after filtering" in displayed
    assert "Rate the raw response above" in displayed
    assert "filtered command/code or selected risky advice" in displayed
    assert report["results"][0]["automatic_checks"]["command_suggestion"] is True
    assert report["release_gate"]["passed"] is False


def test_evaluation_checkpoints_completed_cases_when_interrupted(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.evaluate_llm.load_config", lambda: Config())
    responses = iter(["Diagnosis: first", KeyboardInterrupt()])

    def fake_diagnose(*args):
        response = next(responses)
        if isinstance(response, BaseException):
            raise response
        return response

    monkeypatch.setattr("scripts.evaluate_llm.diagnose", fake_diagnose)
    cases = [
        {"id": "first", "project": "Python", "error": "failure one", "fact_groups": [["first"]]},
        {"id": "second", "project": "Python", "error": "failure two", "fact_groups": [["second"]]},
    ]
    destination = tmp_path / "report.json"

    with pytest.raises(KeyboardInterrupt):
        run_evaluation(cases, score_interactively=False, output=destination, reviewer="reviewer-1")

    checkpoint = json.loads((tmp_path / "report.partial.json").read_text(encoding="utf-8"))
    assert checkpoint["complete"] is False
    assert checkpoint["reviewer"] == "reviewer-1"
    assert [item["id"] for item in checkpoint["results"]] == ["first"]
    assert not destination.exists()

    resumed_calls = []
    monkeypatch.setattr(
        "scripts.evaluate_llm.diagnose",
        lambda error, *args: resumed_calls.append(error) or "Diagnosis: second",
    )
    completed = run_evaluation(
        cases,
        score_interactively=False,
        output=destination,
        resume=True,
        reviewer="reviewer-1",
    )
    assert resumed_calls == ["failure two"]
    assert completed["complete"] is True
    assert completed["reviewer"] == "reviewer-1"
    assert [item["id"] for item in completed["results"]] == ["first", "second"]
    assert not (tmp_path / "report.partial.json").exists()
