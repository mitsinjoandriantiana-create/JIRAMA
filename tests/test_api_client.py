import httpx
import pytest

from src.api_client import ApiClient, ApiError


def test_api_client_sends_bearer_token() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/meters"
        assert request.headers["Authorization"] == "Bearer test-token"
        return httpx.Response(200, json=[{"id": 1}])

    client = ApiClient(
        "https://example.test/api",
        transport=httpx.MockTransport(handle),
    )

    response = client.request("/meters", token="test-token")

    assert response.json() == [{"id": 1}]


def test_api_client_surfaces_api_error_detail() -> None:
    client = ApiClient(
        "https://example.test/api",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(409, json={"detail": "Conflit de données."})
        ),
    )

    with pytest.raises(ApiError, match="Conflit de données.") as error:
        client.request("/invoices", method="POST")

    assert error.value.status_code == 409


def test_api_client_formats_validation_errors() -> None:
    client = ApiClient(
        "https://example.test/api",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                422,
                json={
                    "detail": [
                        {"msg": "Adresse e-mail invalide."},
                        {"msg": "Le mot de passe est trop court."},
                    ]
                },
            )
        ),
    )

    with pytest.raises(
        ApiError,
        match="Adresse e-mail invalide.; Le mot de passe est trop court.",
    ):
        client.request("/auth/register", method="POST")
