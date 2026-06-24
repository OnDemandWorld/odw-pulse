"""VaultClient — async connector for the Vault brand-voice / terminology API.

TSD §2.11 — Vault stores approved brand voices and terminology glossaries
per workspace and market.  This client is the integration seam; the real
HTTP calls will be filled in once the Vault service endpoint is available.
For now every method returns safe mock data so downstream code can be
developed and tested in isolation.
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx

from pulse.config import get_settings


class VaultClient:
    """Async client for the Vault content-repository API.

    Parameters
    ----------
    api_url:
        Base URL of the Vault service.  Falls back to
        ``settings.vault_api_url`` when omitted.
    api_key:
        Bearer token for authentication.  Falls back to
        ``settings.vault_api_key`` when omitted.
    http_client:
        Optional ``httpx.AsyncClient`` — useful for injecting a mock
        transport in tests.
    """

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = get_settings()
        self._api_url = (api_url or settings.vault_api_url or "").rstrip("/")
        self._api_key = api_key or settings.vault_api_key
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=30.0)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying HTTP client if we created it."""
        if self._owns_client:
            await self._http.aclose()

    async def __aenter__(self) -> VaultClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    # ------------------------------------------------------------------
    # Public API (mock implementations)
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        workspace_id: uuid.UUID | str,
    ) -> list[dict[str, Any]]:
        """Search Vault for content matching *query* within a workspace.

        Returns a list of hit dicts.  Currently returns mock data.
        """
        # TODO(TSD §2.11): Replace with real HTTP call once Vault is live.
        # response = await self._http.get(
        #     f"{self._api_url}/search",
        #     params={"q": query, "workspace_id": str(workspace_id)},
        #     headers=self._headers(),
        # )
        # response.raise_for_status()
        # return response.json()
        return [
            {
                "id": "vault-mock-1",
                "title": f"Mock result for '{query}'",
                "workspace_id": str(workspace_id),
                "score": 0.95,
            }
        ]

    async def get_brand_voice(
        self,
        workspace_id: uuid.UUID | str,
    ) -> dict[str, Any]:
        """Return the brand-voice profile for a workspace.

        Returns a dict describing tone, style, do/don't rules.  Currently
        returns mock data.
        """
        # TODO(TSD §2.11): Replace with real HTTP call.
        return {
            "workspace_id": str(workspace_id),
            "tone": "professional",
            "style_guide": "Default mock style guide",
            "rules": ["Avoid jargon", "Be concise"],
        }

    async def get_terminology(
        self,
        workspace_id: uuid.UUID | str,
        market: str,
    ) -> dict[str, Any]:
        """Return approved terminology for a workspace + market pair.

        Returns a dict mapping preferred terms to definitions.  Currently
        returns mock data.
        """
        # TODO(TSD §2.11): Replace with real HTTP call.
        return {
            "workspace_id": str(workspace_id),
            "market": market,
            "terms": {
                "onboarding": "The process of helping a new user get started.",
                "dashboard": "Main overview screen after login.",
            },
        }
