"""Provider contract regressions without requiring live OAuth/WeChat secrets."""

import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest

from app.common.http import HttpClient, http_clients
from app.core.exceptions import CustomException
from app.modules.system.auth import oauth_service, wx_mini_service


def test_oauth_json_and_text_use_shared_client(monkeypatch):
    async def run():
        async def handler(request):
            if request.url.path == "/login/oauth/access_token":
                assert b"client_id=test-client" in request.content
                return httpx.Response(200, json={"access_token": "test-access-token"})
            return httpx.Response(200, text="access_token=test-token&expires_in=3600")

        client = HttpClient("oauth", transport=httpx.MockTransport(handler))
        requested = []

        def get(name):
            requested.append(name)
            return client

        monkeypatch.setattr(http_clients, "get", get)
        assert await oauth_service.exchange_github_token("test-client", "test-secret", "test-code", "https://test/callback") == "test-access-token"
        assert "expires_in=3600" in await oauth_service._http_text("GET", "https://test/token")
        assert requested == ["oauth", "oauth"]
        await client.close()

    asyncio.run(run())


def test_wechat_download_distinguishes_image_and_json_error(monkeypatch):
    async def run():
        calls = 0

        async def handler(request):
            nonlocal calls
            calls += 1
            assert request.url.params["access_token"] == "test-token"
            if calls == 1:
                return httpx.Response(200, content=b"\x89PNG\r\n", headers={"content-type": "image/png"})
            return httpx.Response(200, json={"errcode": 40013, "errmsg": "invalid appid"})

        client = HttpClient("wechat", transport=httpx.MockTransport(handler))
        monkeypatch.setattr(http_clients, "get", lambda _: client)
        monkeypatch.setattr(wx_mini_service, "_get_access_token", AsyncMock(return_value="test-token"))
        assert await wx_mini_service.get_qrcode(None, "test-scene") == b"\x89PNG\r\n"
        with pytest.raises(CustomException, match="40013"):
            await wx_mini_service.get_qrcode(None, "test-scene")
        await client.close()

    asyncio.run(run())
