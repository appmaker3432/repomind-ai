import json
import re
from dataclasses import dataclass

import httpx
from fastapi import HTTPException

OSV_BATCH_URL = "https://api.osv.dev/v1/querybatch"
MAX_DEPENDENCIES = 100
_EXACT_REQUIREMENT = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*==\s*([A-Za-z0-9_.+-]+)\s*(?:#.*)?$")


@dataclass(frozen=True)
class PackageVersion:
    name: str
    version: str
    ecosystem: str
    manifest: str


def parse_requirements(path: str, content: str) -> tuple[list[PackageVersion], int]:
    packages: list[PackageVersion] = []
    unsupported = 0
    for line in content.splitlines():
        normalized = line.strip()
        if not normalized or normalized.startswith("#") or normalized.startswith(("-", "git+", "http:")):
            if normalized and not normalized.startswith("#"):
                unsupported += 1
            continue
        match = _EXACT_REQUIREMENT.fullmatch(normalized)
        if match is None:
            unsupported += 1
            continue
        packages.append(PackageVersion(match[1], match[2], "PyPI", path))
    return packages, unsupported


def parse_package_lock(path: str, content: str) -> tuple[list[PackageVersion], int]:
    try:
        document = json.loads(content)
    except json.JSONDecodeError:
        return [], 1
    packages_node = document.get("packages", {})
    if not isinstance(packages_node, dict):
        return [], 1
    packages: list[PackageVersion] = []
    unsupported = 0
    for key, value in packages_node.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        if not key.startswith("node_modules/"):
            continue
        module_parts = key.split("node_modules/")
        name_parts = module_parts[-1].split("/")
        if len(name_parts) == 2 and name_parts[0].startswith("@"):
            name = "/".join(name_parts)
        elif len(name_parts) == 1:
            name = name_parts[0]
        else:
            unsupported += 1
            continue
        version = value.get("version")
        if not isinstance(version, str):
            unsupported += 1
            continue
        packages.append(PackageVersion(name, version, "npm", path))
    return packages, unsupported


async def audit_dependencies(
    source_files: dict[str, str],
    client: httpx.AsyncClient,
) -> tuple[list[dict], int, int, list[str]]:
    packages: list[PackageVersion] = []
    unsupported = 0
    for path, content in source_files.items():
        name = path.rsplit("/", 1)[-1].lower()
        if name in {"requirements.txt", "requirements-dev.txt", "requirements-prod.txt"}:
            parsed, skipped = parse_requirements(path, content)
        elif name == "package-lock.json":
            parsed, skipped = parse_package_lock(path, content)
        else:
            continue
        packages.extend(parsed)
        unsupported += skipped

    packages = packages[:MAX_DEPENDENCIES]
    if not packages:
        return [], 0, unsupported, [
            "No supported pinned dependency versions were found; supported inputs are exact-pinned Python requirements and npm package-lock.json."
        ]
    batch = [
        {"version": package.version, "package": {"name": package.name, "ecosystem": package.ecosystem}}
        for package in packages
    ]
    try:
        response = await client.post(OSV_BATCH_URL, json={"queries": batch})
    except httpx.TimeoutException as exc:
        raise HTTPException(504, "The OSV vulnerability service timed out.") from exc
    if response.status_code >= 400:
        raise HTTPException(502, f"The OSV vulnerability service returned HTTP {response.status_code}.")
    try:
        results = response.json().get("results", [])
    except (ValueError, AttributeError) as exc:
        raise HTTPException(502, "The OSV service returned an invalid response.") from exc
    if not isinstance(results, list) or len(results) != len(packages):
        raise HTTPException(502, "The OSV service returned an unexpected batch response.")

    findings: list[dict] = []
    for package, result in zip(packages, results):
        if not isinstance(result, dict) or not isinstance(result.get("vulns", []), list):
            raise HTTPException(502, "The OSV service returned an invalid vulnerability record.")
        for vulnerability in result.get("vulns", []):
            if not isinstance(vulnerability, dict):
                continue
            database_specific = vulnerability.get("database_specific")
            database_severity = database_specific.get("severity") if isinstance(database_specific, dict) else None
            severity = database_severity.upper() if isinstance(database_severity, str) else "INFO"
            if severity == "CRITICAL":
                severity = "HIGH"
            if severity not in {"HIGH", "MEDIUM", "LOW"}:
                severity = "INFO"
            findings.append(
                {
                    "title": str(vulnerability.get("id", "OSV vulnerability")),
                    "severity": severity,
                    "confidence": "HIGH",
                    "path": package.manifest,
                    "line": None,
                    "evidence": f"{package.ecosystem} package {package.name}@{package.version} is listed by OSV as affected.",
                    "remediation": "Check the OSV record and upgrade to a fixed version where one is available.",
                    "source": "OSV",
                }
            )
    notes = [f"OSV checked {len(packages)} pinned package versions against its public vulnerability database."]
    if unsupported:
        notes.append(f"Skipped {unsupported} unpinned or unsupported dependency declarations.")
    return findings, len(packages), unsupported, notes
