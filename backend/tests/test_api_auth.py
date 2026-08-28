"""
API-key enforcement tests.

Deliberately NOT marked integration: these hit no live service, and auth is
exactly the kind of thing that must be verified on every run. The app applies
require_api_key globally via FastAPI dependencies, so a regression here would
silently expose every /api/* route.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Must match the key conftest pins into API_KEYS before importing main.
TEST_API_KEY = "test-suite-key"


class TestApiKeyEnforcement:
    def test_api_route_rejects_a_missing_key(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/pairs")
        assert response.status_code == 401

    def test_api_route_rejects_an_invalid_key(self, unauthenticated_client):
        response = unauthenticated_client.get(
            "/api/pairs", headers={"Authorization": "Bearer not-a-real-key"}
        )
        assert response.status_code == 401

    def test_api_route_rejects_a_malformed_authorization_header(self, unauthenticated_client):
        # Right key, wrong scheme — must not be accepted.
        response = unauthenticated_client.get(
            "/api/pairs", headers={"Authorization": TEST_API_KEY}
        )
        assert response.status_code == 401

    @pytest.mark.parametrize("path", ["/", "/health"])
    def test_open_paths_stay_reachable_without_a_key(self, unauthenticated_client, path):
        """Only /api/* is gated — health checks must not require credentials or
        load balancers will mark the service down."""
        response = unauthenticated_client.get(path)
        assert response.status_code == 200

    def test_bearer_scheme_is_case_insensitive(self, unauthenticated_client):
        """require_api_key lowercases the scheme before comparing."""
        response = unauthenticated_client.get(
            "/api/pairs", headers={"Authorization": f"BEARER {TEST_API_KEY}"}
        )
        assert response.status_code != 401
