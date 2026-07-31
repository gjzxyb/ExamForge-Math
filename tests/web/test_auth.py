from fastapi.testclient import TestClient

from examforge.repositories import reset_db_engine_for_tests, reset_vector_for_tests
from examforge.web import create_app


def _auth_client(tmp_path, monkeypatch):
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    import examforge.config.settings as settings_module
    settings_module._store = None
    monkeypatch.setenv("EXAMFORGE_AUTH_ENABLED", "true")
    app = create_app(tmp_path / "data")
    return TestClient(app), settings_module


def test_all_features_require_login_but_health_is_public(tmp_path, monkeypatch):
    client, settings_module = _auth_client(tmp_path, monkeypatch)
    try:
        for path in ("/", "/ingest", "/methods", "/review", "/report", "/qa", "/settings"):
            response = client.get(path, follow_redirects=False)
            assert response.status_code == 303
            assert response.headers["location"].startswith("/login?next=")
        assert client.get("/healthz").status_code == 200
        assert client.get("/login").status_code == 200
        assert client.get("/setup").status_code == 200
        login_html = client.get("/login").text
        assert "auth-page" in login_html
        assert "进入数学方法智能工作区" in login_html
        assert "安全访问 · 本地加密认证" in login_html
        assert 'class="auth-card"' in login_html
    finally:
        reset_db_engine_for_tests()
        reset_vector_for_tests()
        settings_module._store = None


def test_first_setup_login_logout_and_safe_redirect(tmp_path, monkeypatch):
    client, settings_module = _auth_client(tmp_path, monkeypatch)
    try:
        created = client.post("/setup", data={
            "username": "admin",
            "password": "StrongPassword123!",
            "confirm_password": "StrongPassword123!",
        }, follow_redirects=False)
        assert created.status_code == 303
        assert client.get("/methods").status_code == 200

        settings = settings_module.get_settings()
        assert settings.auth.password_hash.startswith("pbkdf2_sha256$")
        assert "StrongPassword123!" not in settings.auth.password_hash
        assert settings.auth.session_secret

        logout = client.post("/logout", follow_redirects=False)
        assert logout.status_code == 303
        assert client.get("/methods", follow_redirects=False).status_code == 303

        failed = client.post("/login", data={
            "username": "admin", "password": "wrong", "next": "/methods",
        })
        assert failed.status_code == 401

        logged_in = client.post("/login", data={
            "username": "admin",
            "password": "StrongPassword123!",
            "next": "https://evil.example/steal",
        }, follow_redirects=False)
        assert logged_in.status_code == 303
        assert logged_in.headers["location"] == "/"
    finally:
        reset_db_engine_for_tests()
        reset_vector_for_tests()
        settings_module._store = None
