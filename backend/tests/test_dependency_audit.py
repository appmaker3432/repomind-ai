import httpx
import pytest

from app.dependency_audit import audit_dependencies, parse_package_lock, parse_requirements


def test_exact_pins_are_parsed_and_unpinned_requirements_are_reported() -> None:
    packages, unsupported = parse_requirements("requirements.txt", "fastapi==0.115.0\nrequests>=2.0\n# comment\n")
    assert [(package.name, package.version, package.ecosystem) for package in packages] == [
        ("fastapi", "0.115.0", "PyPI")
    ]
    assert unsupported == 1


def test_package_lock_includes_direct_and_nested_modules_with_safe_names() -> None:
    packages, unsupported = parse_package_lock(
        "package-lock.json",
        '{"packages":{"node_modules/react":{"version":"18.2.0"},"node_modules/a/node_modules/b":{"version":"1.0.0"}}}',
    )
    assert [(package.name, package.version) for package in packages] == [
        ("react", "18.2.0"),
        ("b", "1.0.0"),
    ]
    assert unsupported == 0


@pytest.mark.asyncio
async def test_osv_results_are_reported_as_scanner_findings() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.osv.dev"
        assert request.url.path == "/v1/querybatch"
        return httpx.Response(200, json={"results": [{"vulns": [{"id": "GHSA-test"}]}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        findings, scanned, unsupported, notes = await audit_dependencies(
            {"requirements.txt": "fastapi==0.115.0"}, client
        )
    assert scanned == 1
    assert unsupported == 0
    assert findings[0]["title"] == "GHSA-test"
    assert findings[0]["source"] == "OSV"
    assert notes
