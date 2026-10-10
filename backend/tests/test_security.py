from app.security import is_sensitive_path


def test_sensitive_paths_are_excluded() -> None:
    for path in (
        ".env",
        ".env.production",
        "secrets/token.json",
        "id_rsa",
        "tls/private.pem",
        ".ssh/config",
        ".aws/credentials",
    ):
        assert is_sensitive_path(path)
    for path in ("src/auth.py", "README.md", "requirements.txt"):
        assert not is_sensitive_path(path)

def test_sensitive_directories_are_excluded() -> None:
    assert is_sensitive_path("private-key/config.py")
