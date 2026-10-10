from .models import ReadmeQuality


_REQUIRED_SECTIONS = (
    ("Project overview", ("description", "about", "overview")),
    ("Installation or setup", ("installation", "install", "setup", "getting started")),
    ("Usage", ("usage", "quick start", "quickstart", "example")),
    ("License", ("license",)),
    ("Contribution guidance", ("contribut",)),
)


def analyze_readme(readme: str) -> ReadmeQuality:
    normalized = readme.lower()
    checks: list[dict[str, str | bool]] = []
    for title, keywords in _REQUIRED_SECTIONS:
        present = any(keyword in normalized for keyword in keywords)
        checks.append(
            {
                "name": title,
                "passed": present,
                "note": "Section or keyword found." if present else "Consider adding a clear section for this topic.",
            }
        )
    score = round(100 * sum(bool(item["passed"]) for item in checks) / len(checks)) if readme else 0
    return ReadmeQuality(score=score, checks=checks)
