"""Best-effort mDNS advertisement for the device-facing Gateway."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from zeroconf import ServiceInfo
from zeroconf.asyncio import AsyncZeroconf

SERVICE_TYPE = "_stackchan-hermes._tcp.local."


class AsyncZeroconfBackend(Protocol):
    async def async_register_service(self, info: ServiceInfo) -> object: ...

    async def async_unregister_service(self, info: ServiceInfo) -> object: ...

    async def async_close(self) -> None: ...


BackendFactory = Callable[[], AsyncZeroconfBackend]


def _default_backend() -> AsyncZeroconfBackend:
    return AsyncZeroconf()


class MdnsAdvertiser:
    """Register one bounded service and degrade cleanly when multicast is unavailable."""

    def __init__(
        self,
        *,
        service_name: str,
        port: int,
        server_version: str,
        hostname: str,
        addresses: tuple[str, ...],
        backend_factory: BackendFactory = _default_backend,
    ) -> None:
        self._backend_factory = backend_factory
        self._backend: AsyncZeroconfBackend | None = None
        self._registered = False
        self.info = ServiceInfo(
            SERVICE_TYPE,
            f"{service_name}.{SERVICE_TYPE}",
            port=port,
            properties={
                "protocol_version": "1",
                "auth_required": "true",
                "server_version": server_version,
            },
            server=f"{hostname}.local.",
            parsed_addresses=list(addresses),
        )

    async def start(self) -> bool:
        if self._registered:
            return True
        try:
            backend = self._backend_factory()
            self._backend = backend
            await backend.async_register_service(self.info)
        except Exception:
            await self._close_backend()
            return False
        self._registered = True
        return True

    async def stop(self) -> None:
        backend = self._backend
        if backend is None:
            return
        try:
            if self._registered:
                await backend.async_unregister_service(self.info)
        finally:
            self._registered = False
            await self._close_backend()

    async def _close_backend(self) -> None:
        backend, self._backend = self._backend, None
        if backend is not None:
            await backend.async_close()
