"""Public asynchronous HTTP API; SDKs can inject the same instrumented client."""

import codecs
import json
import os
import tempfile
from contextlib import asynccontextmanager
from email.message import Message
from http.cookiejar import CookieJar, DefaultCookiePolicy
from pathlib import Path
from urllib.parse import unquote, urlsplit

import aiofiles
import httpx
from fastapi.responses import StreamingResponse

from app.config.setting import settings

from .logging import LoggingTransport, writer


class NoPersistentCookies(DefaultCookiePolicy):
    def set_ok(self, cookie, request):
        return False


class HttpClient:
    def __init__(self, name="default", transport=None):
        self.name = name
        slow = name in ("download", "ai")
        self.raw = httpx.AsyncClient(
            transport=LoggingTransport(name, transport),
            timeout=httpx.Timeout(
                settings.HTTPX_STREAM_READ_TIMEOUT if slow else settings.HTTPX_DEFAULT_TIMEOUT,
                connect=settings.HTTPX_STREAM_CONNECT_TIMEOUT if slow else settings.HTTPX_CONNECT_TIMEOUT,
                pool=settings.HTTPX_POOL_TIMEOUT,
            ),
            follow_redirects=False,
            cookies=CookieJar(policy=NoPersistentCookies()),
            headers={"User-Agent": "ResNexus-HttpClient/1.0", "Accept-Encoding": "gzip, deflate"},
        )

    @staticmethod
    def options(kwargs, stream=False):
        log = {key: kwargs.pop(key) for key in ("log_request_body", "log_response_body", "business", "operator") if key in kwargs}
        log["stream"] = stream
        extensions = dict(kwargs.pop("extensions", {}) or {})
        extensions["http_log"] = {**extensions.get("http_log", {}), **log}
        kwargs["extensions"] = extensions
        bodies = [key for key in ("json", "content", "data") if kwargs.get(key) is not None]
        if len(bodies) > 1:
            raise ValueError("json、content、data 请求体互斥")
        if kwargs.get("files") is not None and any(key in bodies for key in ("json", "content")):
            raise ValueError("文件上传只允许搭配表单 data")
        return kwargs

    async def request(self, method, url, **kwargs):
        response = await self.raw.request(method, url, **self.options(kwargs))
        response.raise_for_status()
        return response

    async def request_json(self, method, url, **kwargs):
        return (await self.request(method, url, **kwargs)).json()

    async def request_text(self, method, url, **kwargs):
        return (await self.request(method, url, **kwargs)).text

    async def get_json(self, url, **kwargs):
        return await self.request_json("GET", url, **kwargs)

    async def post_json(self, url, **kwargs):
        return await self.request_json("POST", url, **kwargs)

    @asynccontextmanager
    async def stream(self, method, url, **kwargs):
        async with self.raw.stream(method, url, **self.options(kwargs, True)) as response:
            response.raise_for_status()
            yield response

    async def download_bytes(self, method, url, **kwargs):
        kwargs.setdefault("log_request_body", False)
        kwargs.setdefault("log_response_body", False)
        return (await self.request(method, url, **kwargs)).content

    async def download_file(self, method, url, destination, *, overwrite=False, **kwargs):
        target = Path(destination).resolve()
        directory = target.is_dir()
        if target.exists() and not directory and not overwrite:
            raise FileExistsError(target)
        temporary = None
        try:
            async with self.stream(method, url, **kwargs) as response:
                if directory:
                    target = target / download_filename(response.headers, url)
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists() and not overwrite:
                    raise FileExistsError(target)
                fd, temporary = tempfile.mkstemp(prefix=".res-nexus-download-", dir=target.parent)
                os.close(fd)
                async with aiofiles.open(temporary, "wb") as output:
                    async for chunk in response.aiter_bytes():
                        await output.write(chunk)
            if overwrite:
                os.replace(temporary, target)
            else:
                # Hard link atomically fails if a concurrent writer owns target.
                os.link(temporary, target)
                os.unlink(temporary)
            return target
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)

    async def proxy_stream(self, method, url, *, incoming_headers=None, forward_headers=("range", "if-range", "if-none-match", "if-modified-since"), **kwargs):
        headers = httpx.Headers(kwargs.pop("headers", {}))
        incoming = httpx.Headers(incoming_headers or {})
        for key in forward_headers:
            if key in incoming:
                headers[key] = incoming[key]
        request = self.raw.build_request(method, url, headers=headers, **self.options(kwargs, True))
        upstream = await self.raw.send(request, stream=True)
        if upstream.status_code >= 400 and upstream.status_code != 416:
            await upstream.aclose()
            upstream.raise_for_status()
        excluded = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailer", "transfer-encoding", "upgrade", "set-cookie"}
        excluded.update(word.strip().lower() for word in upstream.headers.get("connection", "").split(","))
        response_headers = {key: value for key, value in upstream.headers.items() if key.lower() not in excluded}
        response_headers["X-Accel-Buffering"] = "no"

        async def content():
            try:
                async for chunk in upstream.aiter_raw():
                    yield chunk
            finally:
                await upstream.aclose()

        from starlette.background import BackgroundTask

        return StreamingResponse(content(), status_code=upstream.status_code, headers=response_headers, background=BackgroundTask(upstream.aclose))

    async def close(self):
        await self.raw.aclose()


class ClientManager:
    def __init__(self):
        self.clients = {}

    def get(self, name="default"):
        if name not in {"default", "download", "ai", "wechat", "oauth"}:
            raise ValueError("未注册的 HTTP 客户端名称")
        if name not in self.clients:
            self.clients[name] = HttpClient(name)
        return self.clients[name]

    async def start(self, engine):
        await writer.start(engine)

    async def close(self):
        for client in self.clients.values():
            await client.close()
        self.clients.clear()
        await writer.close()


http_clients = ClientManager()


def download_filename(headers, url):
    message = Message()
    message["Content-Disposition"] = headers.get("content-disposition", "")
    name = message.get_filename() or unquote(urlsplit(url).path.rsplit("/", 1)[-1]) or "download"
    name = str(name).replace("\\", "/").rsplit("/", 1)[-1]
    import re

    name = re.sub(r'[\x00-\x1f<>:"/\\|?*]', "_", name).strip(" .")
    if not name or name.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        name = "download"
    return name


async def iter_text(chunks, encoding="utf-8"):
    decoder = codecs.getincrementaldecoder(encoding)()
    async for chunk in chunks:
        text = decoder.decode(chunk)
        if text:
            yield text
    tail = decoder.decode(b"", final=True)
    if tail:
        yield tail


async def iter_lines(chunks):
    buffer = ""
    async for text in iter_text(chunks):
        buffer += text
        while True:
            import re

            match = re.search(r"[\r\n]", buffer)
            if match is None:
                break
            position = match.start()
            if buffer[position] == "\r" and position == len(buffer) - 1:
                break
            width = 2 if buffer[position : position + 2] == "\r\n" else 1
            line, buffer = buffer[:position], buffer[position + width :]
            yield line
    if buffer:
        yield buffer.rstrip("\r")


async def iter_ndjson(chunks):
    async for line in iter_lines(chunks):
        if line.strip():
            yield json.loads(line)


async def iter_sse(chunks):
    event, data = {}, []
    async for line in iter_lines(chunks):
        if not line:
            if data:
                yield {**event, "data": "\n".join(data)}
            event, data = {}, []
        elif not line.startswith(":"):
            key, _, value = line.partition(":")
            value = value[1:] if value.startswith(" ") else value
            if key == "data":
                data.append(value)
            elif key in ("event", "id", "retry"):
                event[key] = value
    if data:
        yield {**event, "data": "\n".join(data)}
