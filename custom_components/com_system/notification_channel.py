"""The channel entity (``notification_channel`` domain) and its manager."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity

from .channels import (
    async_remove_channel_from_devices,
    get_channels,
    unique_id_of,
)
from .const import DATA_CHANNEL_MANAGER, DOMAIN


class NotificationChannelEntity(Entity):
    """A channel: its state is its name, its attributes its default content.

    It only exists to be selected in the action. The channel itself is in the
    hub entry's data, which the entity reads each time it writes its state.
    """

    _attr_should_poll = False
    _attr_icon = "mdi:message-badge"

    def __init__(self, hub: ConfigEntry, channel_id: str) -> None:
        """Initialise from the hub entry and the channel id."""
        self._hub = hub
        self.channel_id = channel_id
        self._attr_unique_id = unique_id_of(hub, channel_id)

    @property
    def _channel(self) -> dict[str, Any]:
        return get_channels(self._hub).get(self.channel_id) or {
            "name": "",
            "defaults": {},
        }

    @property
    def name(self) -> str:
        """Return the channel name."""
        return self._channel["name"]

    @property
    def state(self) -> str:
        """Return the channel name."""
        return self._channel["name"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the channel's default content."""
        return dict(self._channel["defaults"])


class ChannelManager:
    """Keeps the channel entities in step with the hub entry's data.

    The hub's update listener and every change made through the panel call
    ``async_sync``, so channels are added, renamed and removed without
    reloading the hub (which would restart detection).
    """

    def __init__(
        self,
        hass: HomeAssistant,
        hub: ConfigEntry,
        add_entities: Callable[[list[Entity]], None],
    ) -> None:
        """Create the manager; ``add_entities`` is the platform's callback."""
        self._hass = hass
        self._hub = hub
        self._add = add_entities
        self._entities: dict[str, NotificationChannelEntity] = {}
        self._names: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def async_sync(self) -> None:
        """Add, update and remove entities to match the hub's channels."""
        async with self._lock:
            channels = get_channels(self._hub)
            for channel_id in set(self._entities) - set(channels):
                await self._async_remove(channel_id)
            added = [i for i in channels if i not in self._entities]
            for channel_id in added:
                self._entities[channel_id] = NotificationChannelEntity(
                    self._hub, channel_id
                )
                self._names[channel_id] = channels[channel_id]["name"]
            if added:
                self._add([self._entities[i] for i in added])
            for channel_id, channel in channels.items():
                if channel_id in added:
                    continue
                if self._names[channel_id] != channel["name"]:
                    await async_remove_channel_from_devices(
                        self._hass, self._names[channel_id]
                    )
                    self._names[channel_id] = channel["name"]
                self._entities[channel_id].async_write_ha_state()

    async def _async_remove(self, channel_id: str) -> None:
        entity = self._entities.pop(channel_id)
        name = self._names.pop(channel_id)
        entity_id = entity.entity_id
        await entity.async_remove()
        registry = er.async_get(self._hass)
        if entity_id and registry.async_get(entity_id) is not None:
            registry.async_remove(entity_id)
        await async_remove_channel_from_devices(self._hass, name)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add) -> None:
    """Add the hub's channel entities and keep them in step."""
    manager = ChannelManager(hass, entry, add)
    hass.data[DOMAIN][DATA_CHANNEL_MANAGER] = manager
    await manager.async_sync()
