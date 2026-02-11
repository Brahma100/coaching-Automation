from __future__ import annotations

from fastapi.routing import APIRoute
from starlette.requests import Request

from app.request_context import current_endpoint


class EndpointNameRoute(APIRoute):
    def get_route_handler(self):
        original_handler = super().get_route_handler()

        async def custom_handler(request: Request):
            endpoint_label = f"{request.method} {self.path}"
            token = current_endpoint.set(endpoint_label)
            try:
                return await original_handler(request)
            finally:
                current_endpoint.reset(token)

        return custom_handler
