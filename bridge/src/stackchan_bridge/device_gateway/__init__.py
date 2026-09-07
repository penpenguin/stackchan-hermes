"""Authenticated Firmware WebSocket gateway."""

from stackchan_bridge.device_gateway.application import (
    DeviceGatewayConfig,
    create_device_gateway_app,
)

__all__ = ["DeviceGatewayConfig", "create_device_gateway_app"]
