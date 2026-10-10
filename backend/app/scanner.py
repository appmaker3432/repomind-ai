import json
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

from .models import SecurityFinding

MAX_SCANNED_PYTHON_FILES = 30
MAX_BANDIT_SECONDS = 20
REMEDIATION = (
    "Review the reported code in context, remove or replace the risky pattern, "
    "and add a regression test. A scanner finding is not proof of exploitability."
)


def run_bandit(source_files: dict[str, str]) -> tuple[list[SecurityFinding], list[str]]:
    python_files = [
        (path, source)
        for path, source in source_files.items()
        if path.lower().endswith(".py")
    ][:MAX_SCANNED_PYTHON_FILES]
    if not python_files:
        return [], ["Bandit: no eligible Python source files were available to scan."]

    findings: list[SecurityFinding] = []
    notes: list[str] = []
    with tempfile.TemporaryDirectory(prefix="repomind-bandit-") as temporary:
        root = Path(temporary).resolve()
        scan_paths: list[str] = []
        for index, (original_path, source) in enumerate(python_files):
            destination = root / f"{index:04d}.py"
            destination.write_text(source, encoding="utf-8")
            scan_paths.append(str(destination))

        try:
            result = subprocess.run(
                [sys.executable, "-m", "bandit", "-f", "json", "-q", *scan_paths],
                capture_output=True,
                text=True,
                timeout=MAX_BANDIT_SECONDS,
                check=False,
                cwd=root,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("Bandit is not installed. Install backend/requirements.txt and retry.") from exc
        except subprocess.TimeoutExpired as exc:
            return [], ["Bandit timed out; no static-analysis findings are reported."]
        if result.returncode not in (0, 1):
            details = result.stderr.strip()[:300]
            raise RuntimeError(f"Bandit failed to analyze the selected Python files: {details or 'unknown scanner error'}")
        try:
            payload = json.loads(result.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise RuntimeError("Bandit returned invalid JSON output.") from exc
        path_by_temporary = {
            str(root / f"{index:04d}.py"): original_path
            for index, (original_path, _) in enumerate(python_files)
        }
        for item in payload.get("results", []):
            severity = str(item.get("issue_severity", "")).upper()
            confidence = str(item.get("issue_confidence", "")).upper()
            if severity not in {"HIGH", "MEDIUM", "LOW"}:
                severity = "INFO"
            if confidence not in {"HIGH", "MEDIUM", "LOW"}:
                confidence = "UNKNOWN"
            temporary_path = str(Path(item.get("filename", "")).resolve())
            findings.append(
                SecurityFinding(
                    title=str(item.get("test_name", "Bandit finding")),
                    severity=severity,
                    confidence=confidence,
                    path=path_by_temporary.get(temporary_path, "unknown"),
                    line=item.get("line_number") if isinstance(item.get("line_number"), int) else None,
                    evidence=str(item.get("issue_text", "Scanner reported a potential issue."))[:500],
                    remediation=REMEDIATION,
                    source="Bandit",
                )
            )
        if len(source_files) > len(python_files):
            notes.append(f"Bandit scanned {len(python_files)} of at most {MAX_SCANNED_PYTHON_FILES} eligible Python files.")
    return findings, notes
