"""Auth endpoint tests — 6 tests covering registration, login, and token validation."""


class TestRegister:
    def test_register_success(self, client):
        """New user registration returns 201 with a JWT."""
        response = client.post(
            "/auth/register",
            json={"username": "newuser", "password": "securepass"},
        )
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_register_duplicate_username(self, client):
        """Registering an existing username returns 400."""
        client.post(
            "/auth/register",
            json={"username": "dupuser", "password": "pass1234"},
        )
        response = client.post(
            "/auth/register",
            json={"username": "dupuser", "password": "otherpass"},
        )
        assert response.status_code == 400
        assert "already taken" in response.json()["detail"].lower()


class TestLogin:
    def test_login_success(self, client):
        """Valid credentials return a JWT."""
        client.post(
            "/auth/register",
            json={"username": "loginuser", "password": "mypass123"},
        )
        response = client.post(
            "/auth/login",
            json={"username": "loginuser", "password": "mypass123"},
        )
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_login_wrong_password(self, client):
        """Wrong password returns 401."""
        client.post(
            "/auth/register",
            json={"username": "wrongpwuser", "password": "correct"},
        )
        response = client.post(
            "/auth/login",
            json={"username": "wrongpwuser", "password": "incorrect"},
        )
        assert response.status_code == 401


class TestProtectedAccess:
    def test_missing_token(self, client):
        """Accessing a protected endpoint without a token returns 401."""
        response = client.get("/analytics/kpi-summary")
        assert response.status_code == 401

    def test_invalid_token(self, client):
        """An invalid JWT returns 401."""
        response = client.get(
            "/analytics/kpi-summary",
            headers={"Authorization": "Bearer invalidtoken"},
        )
        assert response.status_code == 401


class TestApiKey:
    def test_generate_api_key_success(self, client, auth_headers):
        """Users can generate long-lived API keys using their normal token."""
        response = client.post("/auth/api-key", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
