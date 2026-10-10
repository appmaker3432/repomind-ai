import pytest

from app.scanner import run_bandit


def test_bandit_reports_source_path_and_line_without_running_source() -> None:
    findings, notes = run_bandit(
        {
            "src/example.py": "import subprocess\nsubprocess.Popen('echo unsafe', shell=True)\n",
        }
    )
    assert any(
        finding.source == "Bandit"
        and finding.path == "src/example.py"
        and finding.line is not None
        for finding in findings
    )
    assert notes == []


def test_bandit_returns_an_explicit_note_when_no_python_files_exist() -> None:
    findings, notes = run_bandit({"package.json": "{}"})
    assert findings == []
    assert "no eligible Python" in notes[0]
