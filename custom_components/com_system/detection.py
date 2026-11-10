"""Detection of receivers, run by the hub.

The hub detects on every setup (pending discovery flows live in memory only),
again after device registry changes and on a timer. Each detection:

- raises one discovery flow per candidate, with the source device as the
  flow's unique id, so repeated detection never duplicates a flow and
  configured or ignored sources are not offered again;
- leaves receivers whose source disappeared alone (they are shown as
  unavailable, not removed);
- reloads receivers whose source reappeared, so they attach to it again.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta

from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY, ConfigEntry
from homeassistant.const import EVENT_SERVICE_REGISTERED, EVENT_SERVICE_REMOVED
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_DISCOVERY_TYPE,
    CONF_NAME,
    CONF_RECEIVER_TYPE,
    CONF_SOURCE_ID,
    DETECTION_DEBOUNCE_SECONDS,
    DETECTION_INTERVAL_SECONDS,
    DOMAIN,
)
from .receiver import Receiver
from .receiver_type import ReceiverType, get_receiver_type, receiver_types

_LOGGER = logging.getLogger(__name__)


def discovery_unique_id(type_id: str, source_id: str) -> str:
    """Return the unique id of a receiver for a source device."""
    return f"{type_id}_{source_id}"


class ReceiverDetector:
    """Detects receivers and raises discovery flows for them."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise the detector."""
        self._hass = hass
        self._available: dict[str, bool] = {}
        self._unsubscribers: list[Callable[[], None]] = []
        self._debouncer = Debouncer(
            hass,
            _LOGGER,
            cooldown=DETECTION_DEBOUNCE_SECONDS,
            immediate=False,
            function=self.async_detect,
        )

    @callback
    def async_start(self) -> None:
        """Start detecting on registry changes and on a timer."""
        self._unsubscribers.append(
            self._hass.bus.async_listen(
                dr.EVENT_DEVICE_REGISTRY_UPDATED, self._registry_updated
            )
        )
        for event_type in (EVENT_SERVICE_REGISTERED, EVENT_SERVICE_REMOVED):
            self._unsubscribers.append(
                self._hass.bus.async_listen(event_type, self._service_changed)
            )
        self._unsubscribers.append(
            async_track_time_interval(
                self._hass,
                self._interval,
                timedelta(seconds=DETECTION_INTERVAL_SECONDS),
            )
        )

    @callback
    def async_start_detection(self, hass: HomeAssistant) -> None:
        """Run the first detection (called once Home Assistant has started)."""
        hass.async_create_task(self.async_detect(), "com_system initial detection")

    @callback
    def async_stop(self) -> None:
        """Stop detecting."""
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()
        self._debouncer.async_shutdown()

    @callback
    def _registry_updated(self, event: Event) -> None:
        self._debouncer.async_schedule_call()

    @callback
    def _service_changed(self, event: Event) -> None:
        """Scripts are services, so detect again when one is (un)registered."""
        if event.data.get("domain") == "script":
            self._debouncer.async_schedule_call()

    async def _interval(self, now: object) -> None:
        await self.async_detect()

    async def async_detect(self) -> None:
        """Detect once: raise discoveries and reload returned receivers."""
        await self._async_discover()
        await self._async_reattach()

    async def _async_discover(self) -> None:
        hass = self._hass
        known = {
            entry.unique_id
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.unique_id is not None
        }
        for receiver_type in receiver_types():
            if not receiver_type.discoverable:
                continue
            try:
                candidates = await receiver_type.async_detect(hass)
            except Exception:
                _LOGGER.exception(
                    "Detecting %s receivers failed", receiver_type.type_id
                )
                continue
            for candidate in candidates:
                unique_id = discovery_unique_id(
                    receiver_type.type_id, candidate.source_id
                )
                # Configured and ignored receivers are entries, so they are
                # skipped here; a deleted receiver is not, so it is offered.
                if unique_id in known:
                    continue
                await hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_INTEGRATION_DISCOVERY},
                    data={
                        CONF_DISCOVERY_TYPE: receiver_type.type_id,
                        CONF_SOURCE_ID: candidate.source_id,
                        CONF_NAME: candidate.name,
                    },
                )

    async def _async_reattach(self) -> None:
        """Reload receivers whose source device came back."""
        hass = self._hass
        seen: set[str] = set()
        for entry in hass.config_entries.async_entries(DOMAIN):
            receiver_type = _type_for(entry)
            if receiver_type is None or not receiver_type.discoverable:
                continue
            receiver = Receiver.from_entry(entry)
            available = receiver_type.is_source_available(hass, receiver)
            seen.add(entry.entry_id)
            was_available = self._available.get(entry.entry_id)
            self._available[entry.entry_id] = available
            if available and was_available is False:
                _LOGGER.debug("Source of %s returned, reloading", entry.title)
                await hass.config_entries.async_reload(entry.entry_id)
        for entry_id in set(self._available) - seen:
            del self._available[entry_id]


def _type_for(entry: ConfigEntry) -> ReceiverType | None:
    """Return the registered type of a receiver entry, if it has one."""
    return get_receiver_type(entry.data.get(CONF_RECEIVER_TYPE, ""))
