import re
from pathlib import PurePosixPath


_SENSITIVE_NAME_PARTS = ("secret", "credential", "private_key", "private-key")
_SENSITIVE_SUFFIXES = (".pem", ".key", ".p12", ".pfx")
_ENV_FILE_NAMES = {".env", ".env.local", ".env.production", ".npmrc", ".pypirc"}
_PRIVATE_KEY_NAMES = {"id_rsa", "id_ed25519", "id_ecdsa", "id_dsa"}
_SENSITIVE_DIRECTORIES = {"secrets", "credentials", ".ssh", ".aws", ".gnupg"}
_POSSIBLE_SECRET = re.compile(
    r"(?i)(?:"
    r"(?:api[_-]?key|secret|password|token|authorization|bearer|private[_-]?key)"
    r"\s*[:=]\s*['\"]?[^'\"\s,;]{8,}['\"]?"
    r"|\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16})\b"
    r"|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    r")"
)


def is_sensitive_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    parts = PurePosixPath(normalized).parts
    name = parts[-1] if parts else normalized
    return (
        any(part in _SENSITIVE_DIRECTORIES for part in parts)
        or name in _ENV_FILE_NAMES
        or name in _PRIVATE_KEY_NAMES
        or name.startswith(".env.")
        or name.endswith(_SENSITIVE_SUFFIXES)
        or any(marker in part for part in parts for marker in _SENSITIVE_NAME_PARTS)
    )


def redact_sensitive_lines(text: str) -> str:
    return "\n".join(
        "[redacted: possible secret]" if _POSSIBLE_SECRET.search(line) else line
        for line in text.splitlines()
    )
