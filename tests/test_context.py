from errdoc.context import detect_context


def test_detect_context_reports_platform_and_project(tmp_path):
    (tmp_path / "manage.py").write_text("", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    result = detect_context(tmp_path)
    assert result["os"]
    assert result["python"]
    assert "Django" in result["project"]
    assert "Git" in result["project"]


def test_detect_context_unknown_project(tmp_path):
    result = detect_context(tmp_path)
    assert result["project"] == "Unknown"
    assert "cwd" not in result

def test_detect_context_node_and_python_markers(tmp_path):
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
    result = detect_context(tmp_path)
    assert "Node.js" in result["project"]
    assert "Python" in result["project"]
