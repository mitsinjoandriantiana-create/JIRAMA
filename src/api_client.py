from typing import Any

import httpx


class ApiError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ApiClient:
    def __init__(
        self,
        base_url: str,
        timeout: float = 15.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    def request(
        self,
        path: str,
        method: str = "GET",
        *,
        token: str | None = None,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
    ) -> httpx.Response:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
                response = client.request(
                    method,
                    f"{self.base_url}{path}",
                    headers=headers,
                    params=params,
                    json=json,
                    files=files,
                )
        except httpx.RequestError as exc:
            raise ApiError(
                "Impossible de joindre l'API. Vérifie que le serveur FastAPI "
                "est démarré."
            ) from exc

        if not response.is_success:
            detail = None
            try:
                payload = response.json()
            except ValueError:
                payload = None
            if isinstance(payload, dict):
                detail = payload.get("detail")
            if isinstance(detail, str):
                message = detail
            elif isinstance(detail, list):
                messages = [
                    item["msg"]
                    for item in detail
                    if isinstance(item, dict) and isinstance(item.get("msg"), str)
                ]
                message = "; ".join(messages) or f"Erreur API {response.status_code}."
            else:
                message = f"Erreur API {response.status_code}."
            raise ApiError(message, response.status_code)
        return response
