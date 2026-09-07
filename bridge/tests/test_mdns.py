from __future__ import annotations

import pytest
from stackchan_bridge.discovery.mdns import MdnsAdvertiser
from zeroconf import ServiceInfo


class FakeAsyncZeroconf:
    def __init__(self) -> None:
        self.registered: list[ServiceInfo] = []
        self.unregistered: list[ServiceInfo] = []
        self.closed = False

    async def async_register_service(self, info: ServiceInfo) -> None:
        self.registered.append(info)

    async def async_unregister_service(self, info: ServiceInfo) -> None:
        self.unregistered.append(info)

    async def async_close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_mdns_advertises_required_service_and_closes_cleanly() -> None:
    backend = FakeAsyncZeroconf()
    advertiser = MdnsAdvertiser(
        service_name="stackchan-bridge",
        port=8765,
        server_version="0.1.0",
        hostname="bridge-host",
        addresses=("192.0.2.20",),
        backend_factory=lambda: backend,
    )

    assert await advertiser.start() is True
    assert await advertiser.start() is True
    await advertiser.stop()

    assert len(backend.registered) == 1
    info = backend.registered[0]
    assert info.type == "_stackchan-hermes._tcp.local."
    assert info.name == "stackchan-bridge._stackchan-hermes._tcp.local."
    assert info.port == 8765
    assert info.server == "bridge-host.local."
    assert info.parsed_addresses() == ["192.0.2.20"]
    assert info.decoded_properties == {
        "protocol_version": "1",
        "auth_required": "true",
        "server_version": "0.1.0",
    }
    assert backend.unregistered == [info]
    assert backend.closed is True


@pytest.mark.asyncio
async def test_mdns_registration_failure_closes_backend_and_allows_fixed_url_fallback() -> None:
    class FailingBackend(FakeAsyncZeroconf):
        async def async_register_service(self, info: ServiceInfo) -> None:
            self.registered.append(info)
            raise OSError("multicast unavailable")

    backend = FailingBackend()
    advertiser = MdnsAdvertiser(
        service_name="stackchan-bridge",
        port=8765,
        server_version="0.1.0",
        hostname="bridge-host",
        addresses=(),
        backend_factory=lambda: backend,
    )

    assert await advertiser.start() is False
    await advertiser.stop()

    assert len(backend.registered) == 1
    assert backend.unregistered == []
    assert backend.closed is True
