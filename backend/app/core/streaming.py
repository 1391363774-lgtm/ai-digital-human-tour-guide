"""Explicit generator lifetime, including an ASGI 2.4 send() failure."""
import anyio
from starlette.responses import StreamingResponse


class ClosingStreamingResponse(StreamingResponse):
    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            with anyio.CancelScope(shield=True):
                await self.body_iterator.aclose()
