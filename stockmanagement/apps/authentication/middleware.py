from __future__ import annotations

import asyncio
import time


class ExecutionTimeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.is_async = asyncio.iscoroutinefunction(get_response)

    def __call__(self, request):
        if self.is_async:
            return self.async_call(request)
        return self.sync_call(request)

    def sync_call(self, request):
        start_time = time.perf_counter()
        response = self.get_response(request)
        duration = (time.perf_counter() - start_time) * 1000
        response['X-Execution-Time'] = f'{duration:.2f}ms'
        return response

    async def async_call(self, request):
        start_time = time.perf_counter()
        response = await self.get_response(request)
        duration = (time.perf_counter() - start_time) * 1000
        response.headers['X-Execution-Time'] = f'{duration:.2f}ms'
        return response
