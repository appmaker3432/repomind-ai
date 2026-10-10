from app.security import is_sensitive_path, redact_sensitive_lines


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


def test_possible_secret_lines_are_redacted() -> None:
    result = redact_sensitive_lines('password = "ordinary-looking-secret-value"\nprint("safe")')
    assert "ordinary-looking-secret-value" not in result
    assert "print" in result


def test_known_token_formats_and_sensitive_directories_are_redacted() -> None:
    assert is_sensitive_path("private-key/config.py")
    result = redact_sensitive_lines("token = ghp_abcdefghijklmnopqrstuvwxyz123456\n")
    assert "ghp_" not in result
    assert "plain-token-value" not in redact_sensitive_lines("API_KEY=plain-token-value")
