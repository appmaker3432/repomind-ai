from abc import ABC, abstractmethod
import json

from ..github_client import RepositoryReference


def parse_ai_analysis(content: str) -> tuple[str, str]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("AI provider did not return the required JSON summary and architecture explanation.") from exc
    if not isinstance(payload, dict):
        raise ValueError("AI provider returned an unexpected analysis structure.")
    summary = payload.get("summary")
    architecture = payload.get("architecture")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("AI provider returned an empty project summary.")
    if not isinstance(architecture, str) or not architecture.strip():
        raise ValueError("AI provider returned an empty architecture explanation.")
    return summary.strip(), architecture.strip()


class AnalysisProvider(ABC):
    name: str

    @abstractmethod
    async def analyze(self, repository: RepositoryReference, context: str) -> tuple[str, str, str]:
        """Return an AI summary, architecture explanation, and model identifier."""
