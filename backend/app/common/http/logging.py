"""Transport interception: captures while consumed, never pre-reads a stream."""

import asyncio
import gzip
import json
import os
import tempfile
import time
import uuid
import zlib
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime

import aiofiles
import httpx

from app.config.setting import settings
from app.core.logger import get_correlation_id, logger

from .storage import TZ, initial_months, persist, prepare

_context = ContextVar("http_log_context", default=None)


@contextmanager
def http_context(**options):
    token = _context.set({**(_context.get() or {}), **options})
    try:
        yield
    finally:
        _context.reset(token)


def bind_http_operator(username):
    _context.set({**(_context.get() or {}), "operator": username})


def is_json(content_type):
    mime = content_type.split(";")[0].strip().lower()
    return mime == "application/json" or mime.endswith("+json")


class Capture:
    def __init__(self, enabled):
        self.enabled = enabled
        self.size = 0
        self.path = None
        self.failed = False

    async def add(self, data):
        self.size += len(data)
        if self.enabled and not self.failed:
            try:
                if self.path is None:
                    fd, self.path = tempfile.mkstemp(prefix="res-nexus-http-")
                    os.close(fd)
                async with aiofiles.open(self.path, "ab") as output:
                    await output.write(data)
            except Exception:
                self.failed = True
                logger.exception("HTTP body capture failed")

    def cleanup(self):
        if self.path:
            try:
                os.unlink(self.path)
            except OSError:
                logger.warning("HTTP temporary body cleanup failed")

    def read(self, encoding=None, charset="utf-8"):
        if not self.path:
            return ""
        with open(self.path, "rb") as source:
            data = source.read()
        if encoding == "gzip":
            data = gzip.decompress(data)
        elif encoding == "deflate":
            data = zlib.decompress(data)
        return data.decode(charset, errors="strict")


class LogWriter:
    def __init__(self):
        self.queue = asyncio.Queue(maxsize=settings.HTTPX_LOG_QUEUE_SIZE)
        self.task = None
        self.engine = None

    async def start(self, engine):
        self.engine = engine
        for month in initial_months():
            await prepare(engine, month)
        self.task = asyncio.create_task(self.run(), name="http-log-writer")

    def submit(self, record, captures, encoding):
        logger.bind(http_request_id=record["id"]).info("HTTP {}", json.dumps(record, ensure_ascii=False, default=str))
        if self.task is None:
            for capture in captures.values():
                capture.cleanup()
            return
        try:
            self.queue.put_nowait((record, captures, encoding))
        except asyncio.QueueFull:
            for capture in captures.values():
                capture.cleanup()
            logger.error("HTTP log queue full: database record lost id={}", record["id"])

    async def run(self):
        while True:
            record, captures, encoding = await self.queue.get()
            try:
                bodies = {}
                for side, capture in captures.items():
                    if capture.enabled and not capture.failed:
                        try:
                            bodies[side] = await asyncio.to_thread(capture.read, encoding if side == "response" else None)
                        except Exception:
                            record[side + "_body_state"] = "failed"
                            logger.exception("HTTP body decoding failed id={}", record["id"])
                await persist(self.engine, record, bodies)
            except Exception:
                logger.exception("HTTP log persistence failed id={}", record["id"])
            finally:
                for capture in captures.values():
                    capture.cleanup()
                self.queue.task_done()

    async def close(self):
        if self.task is None:
            return
        try:
            await asyncio.wait_for(self.queue.join(), 15)
        except TimeoutError:
            logger.error("HTTP log shutdown drain timed out")
        self.task.cancel()
        await asyncio.gather(self.task, return_exceptions=True)
        self.task = None
        while not self.queue.empty():
            _, captures, _ = self.queue.get_nowait()
            for capture in captures.values():
                capture.cleanup()
            self.queue.task_done()


writer = LogWriter()


class TappedStream(httpx.AsyncByteStream):
    def __init__(self, source, capture, finish=None):
        self.source, self.capture, self.finish = source, capture, finish

    async def __aiter__(self):
        try:
            async for chunk in self.source:
                await self.capture.add(chunk)
                yield chunk
        except BaseException as exc:
            if self.finish:
                self.finish("cancelled" if isinstance(exc, asyncio.CancelledError) else "failed", type(exc).__name__)
            raise
        else:
            if self.finish:
                self.finish(None, None)

    async def aclose(self):
        try:
            await self.source.aclose()
        finally:
            if self.finish:
                self.finish("closed", None)


class LoggingTransport(httpx.AsyncBaseTransport):
    def __init__(self, service, transport=None):
        self.service = service
        self.transport = transport or httpx.AsyncHTTPTransport(
            retries=0, limits=httpx.Limits(max_connections=settings.HTTPX_MAX_CONNECTIONS, max_keepalive_connections=settings.HTTPX_MAX_KEEPALIVE_CONNECTIONS)
        )

    async def handle_async_request(self, request):
        options = {**(_context.get() or {}), **request.extensions.get("http_log", {})}
        request_capture = Capture(options.get("log_request_body", is_json(request.headers.get("content-type", ""))))
        response_capture = Capture(False)
        began = time.monotonic()
        record = {
            "id": uuid.uuid4().hex,
            "started_at": datetime.now(TZ).replace(tzinfo=None),
            "service": self.service,
            "business": options.get("business"),
            "operator": options.get("operator"),
            "correlation_id": get_correlation_id(),
            "call_id": options.get("call_id") or uuid.uuid4().hex,
            "attempt": options.get("attempt", 0),
            "method": request.method,
            "url": str(request.url),
            "request_headers": json.dumps(list(request.headers.multi_items()), ensure_ascii=False),
            "response_headers": None,
            "status_code": None,
            "first_response_ms": None,
        }
        try:
            cached_request = request.content
        except httpx.RequestNotRead:
            request_capture.enabled = options.get("log_request_body", False)
            request.stream = TappedStream(request.stream, request_capture)
        else:
            await request_capture.add(cached_request)
        done = False
        encoding = None

        def finish(result, error):
            nonlocal done
            if done:
                return
            done = True
            if result == "closed" and record["status_code"] is not None and record["status_code"] >= 400:
                result = "failed"
            if result in {"closed", "cancelled", "failed"} and response_capture.enabled:
                response_capture.failed = True
            record.update(
                result=result or ("success" if record["status_code"] is not None and record["status_code"] < 400 else "failed"),
                error=error,
                duration_ms=round((time.monotonic() - began) * 1000, 3),
                request_bytes=request_capture.size,
                response_bytes=response_capture.size,
            )
            for side, capture in (("request", request_capture), ("response", response_capture)):
                record[side + "_body_state"] = "failed" if capture.failed else ("pending" if capture.enabled else "not_recorded")
            writer.submit(record, {"request": request_capture, "response": response_capture}, encoding)

        try:
            response = await self.transport.handle_async_request(request)
            record.update(
                {
                    "status_code": response.status_code,
                    "first_response_ms": round((time.monotonic() - began) * 1000, 3),
                    "response_headers": json.dumps(list(response.headers.multi_items()), ensure_ascii=False),
                }
            )
            default_body = is_json(response.headers.get("content-type", "")) and not response.headers.get("content-disposition", "").lower().startswith("attachment")
            response_capture.enabled = options.get("log_response_body", default_body) and not options.get("stream", False)
            encoding = response.headers.get("content-encoding")
            response.stream = TappedStream(response.stream, response_capture, finish)
            if response.is_stream_consumed:
                await response_capture.add(response.content)
                encoding = None
                finish(None, None)
            return response
        except BaseException as exc:
            finish("cancelled" if isinstance(exc, asyncio.CancelledError) else "failed", type(exc).__name__)
            raise

    async def aclose(self):
        await self.transport.aclose()
