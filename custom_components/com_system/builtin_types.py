"""The built-in receiver types and how their receivers are detected.

Delivery for each type is added with the type's own feature; here they only
declare how receivers are found. Detection reads Home Assistant's registries
and config entries, so it needs no access to the source integration itself
and finds nothing when the integration is not installed.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import SOURCE_IGNORE, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .const import (
    RECEIVER_TYPE_ALEXA_MEDIA,
    RECEIVER_TYPE_MOBILE_APP,
    RECEIVER_TYPE_MUSIC_ASSISTANT,
    RECEIVER_TYPE_PERSISTENT_NOTIFICATION,
    RECEIVER_TYPE_PUSHOVER,
    RECEIVER_TYPE_WEBOSTV,
)
from .mobile_app import (
    async_deliver_mobile_app,
    audience_of,
    linked_person,
    mobile_app_people,
)
from .pushover import (
    PUSHOVER_DOMAIN,
    async_deliver_pushover,
    async_entry_devices,
    source_entry,
    source_id_of,
)
from .receiver import Receiver
from .receiver_type import (
    DiscoveryCandidate,
    ReceiverType,
    get_receiver_type,
    register_receiver_type,
)
from .webostv import async_deliver_webostv

ALEXA_NOTIFY_SERVICE = "alexa_media"


def _source_entries(hass: HomeAssistant, domain: str) -> list[ConfigEntry]:
    """Return the config entries of an integration, skipping ignored and disabled."""
    return [
        entry
        for entry in hass.config_entries.async_entries(domain)
        if entry.source != SOURCE_IGNORE and entry.disabled_by is None
    ]


class DeviceReceiverType(ReceiverType):
    """A type with one receiver per device of another integration.

    The source id is the device's identifier in the integration's domain.
    """

    discoverable = True
    source_domain: str

    async def async_detect(self, hass: HomeAssistant) -> list[DiscoveryCandidate]:
        """Return a candidate for each device of the source integration."""
        device_registry = dr.async_get(hass)
        candidates: dict[str, DiscoveryCandidate] = {}
        for entry in _source_entries(hass, self.source_domain):
            for device in dr.async_entries_for_config_entry(
                device_registry, entry.entry_id
            ):
                if device.disabled:
                    continue
                for domain, identifier in device.identifiers:
                    if domain == self.source_domain:
                        name = device.name_by_user or device.name or identifier
                        candidates[identifier] = DiscoveryCandidate(identifier, name)
        return list(candidates.values())

    def source_device_identifiers(
        self, receiver: Receiver
    ) -> set[tuple[str, str]] | None:
        """Attach the receiver's entities to the source device."""
        if receiver.source_id is None:
            return None
        return {(self.source_domain, receiver.source_id)}

    def is_source_available(self, hass: HomeAssistant, receiver: Receiver) -> bool:
        """Return whether the source device is still registered."""
        if receiver.source_id is None:
            return False
        device = dr.async_get(hass).async_get_device(
            identifiers={(self.source_domain, receiver.source_id)}
        )
        return device is not None


class EntryReceiverType(ReceiverType):
    """A type with one receiver per config entry of another integration.

    The source id is the entry's unique id, or its entry id without one.
    """

    discoverable = True
    source_domain: str

    async def async_detect(self, hass: HomeAssistant) -> list[DiscoveryCandidate]:
        """Return a candidate for each config entry of the source integration."""
        return [
            DiscoveryCandidate(entry.unique_id or entry.entry_id, entry.title)
            for entry in _source_entries(hass, self.source_domain)
        ]

    def is_source_available(self, hass: HomeAssistant, receiver: Receiver) -> bool:
        """Return whether the source config entry still exists."""
        return any(
            receiver.source_id in (entry.unique_id, entry.entry_id)
            for entry in _source_entries(hass, self.source_domain)
        )


class MobileAppReceiverType(DeviceReceiverType):
    """One receiver per registered mobile app device."""

    type_id = RECEIVER_TYPE_MOBILE_APP
    name = "Mobile app"
    source_domain = "mobile_app"
    capabilities = frozenset({"title"})
    # The person comes from the registering user, not from the options.
    supports_people = False

    async def async_deliver(
        self, hass: HomeAssistant, receiver: Receiver, notification: Mapping[str, Any]
    ) -> list[str]:
        """Call the device's ``notify.mobile_app_*`` action."""
        return await async_deliver_mobile_app(hass, receiver, notification)

    def linked_person(self, hass: HomeAssistant, receiver: Receiver) -> str | None:
        """Return the person the device's user or tracker links to."""
        return linked_person(hass, receiver)

    def associated_people(
        self, hass: HomeAssistant, receiver: Receiver
    ) -> tuple[str, ...]:
        """Return no one for a shared device, else the linked person."""
        return mobile_app_people(hass, receiver)

    def audience(self, hass: HomeAssistant, receiver: Receiver) -> str:
        """Return ``personal`` or ``shared`` for the receiver."""
        return audience_of(hass, receiver)


class AlexaMediaReceiverType(DeviceReceiverType):
    """One receiver per Echo device of Alexa Media Player (custom)."""

    type_id = RECEIVER_TYPE_ALEXA_MEDIA
    name = "Alexa Media Player"
    source_domain = "alexa_media"
    capabilities = frozenset({"title"})

    async def async_deliver(
        self, hass: HomeAssistant, receiver: Receiver, notification: Mapping[str, Any]
    ) -> list[str]:
        """Announce the notification on the Echo through ``notify.alexa_media``.

        The integration registers one notify action for all its devices and
        picks the device from ``target``, which matches the device's serial
        number (the receiver's source id). ``type: announce`` is used, so the
        message is spoken and the title is shown on devices with a screen.
        """
        if receiver.source_id is None:
            raise HomeAssistantError("The Echo device is not known")
        if not hass.services.has_service("notify", ALEXA_NOTIFY_SERVICE):
            raise HomeAssistantError(
                f"The action notify.{ALEXA_NOTIFY_SERVICE} is not available; "
                "is Alexa Media Player installed and loaded?"
            )
        data: dict[str, Any] = {"type": "announce"}
        message: dict[str, Any] = {
            "message": notification["message"],
            "target": [receiver.source_id],
            "data": data,
        }
        if notification.get("title"):
            message["title"] = notification["title"]
        await hass.services.async_call(
            "notify", ALEXA_NOTIFY_SERVICE, message, blocking=True
        )
        return []


class PersistentNotificationReceiverType(ReceiverType):
    """A single receiver that posts to the Home Assistant notification area."""

    type_id = RECEIVER_TYPE_PERSISTENT_NOTIFICATION
    name = "Persistent notification"
    discoverable = True
    # Every user sees the same notifications, so there is no person.
    supports_people = False
    SOURCE_ID = "persistent_notification"

    async def async_detect(self, hass: HomeAssistant) -> list[DiscoveryCandidate]:
        """Always offer the one receiver."""
        return [DiscoveryCandidate(self.SOURCE_ID, self.name)]

    async def async_deliver(
        self, hass: HomeAssistant, receiver: Receiver, notification: Mapping[str, Any]
    ) -> list[str]:
        """Create a persistent notification.

        Create-only: no ``notification_id`` is sent, so Home Assistant makes a
        new notification each time and Com System never replaces or dismisses
        one. Only the message and title are supported.
        """
        data: dict[str, Any] = {"message": notification["message"]}
        if notification.get("title"):
            data["title"] = notification["title"]
        await hass.services.async_call(
            "persistent_notification", "create", data, blocking=True
        )
        return []


class PushoverReceiverType(ReceiverType):
    """One receiver per device (target) of each Pushover config entry."""

    type_id = RECEIVER_TYPE_PUSHOVER
    name = "Pushover"
    capabilities = frozenset({"title"})
    discoverable = True
    # Pushover has no user link: the person is chosen in the options
    # (supports_people stays True).

    async def async_detect(self, hass: HomeAssistant) -> list[DiscoveryCandidate]:
        """Return a candidate for each device of each loaded Pushover entry."""
        candidates = []
        for entry in _source_entries(hass, PUSHOVER_DOMAIN):
            for device in await async_entry_devices(hass, entry):
                candidates.append(
                    DiscoveryCandidate(
                        source_id_of(entry, device), f"{entry.title} {device}"
                    )
                )
        return candidates

    def is_source_available(self, hass: HomeAssistant, receiver: Receiver) -> bool:
        """Return whether the Pushover config entry still exists."""
        return source_entry(hass, receiver) is not None

    async def async_deliver(
        self, hass: HomeAssistant, receiver: Receiver, notification: Mapping[str, Any]
    ) -> list[str]:
        """Call the entry's ``notify.<name>`` action for the device."""
        return await async_deliver_pushover(hass, receiver, notification)


class WebOSTVReceiverType(EntryReceiverType):
    """One receiver per webOS TV config entry."""

    type_id = RECEIVER_TYPE_WEBOSTV
    name = "webOS TV"
    source_domain = "webostv"
    # A TV is shared, so it has no person (and no people option).
    supports_people = False

    def source_device_identifiers(
        self, receiver: Receiver
    ) -> set[tuple[str, str]] | None:
        """Attach to the TV's device, so the area is the TV's area.

        The integration's device identifier is the config entry's unique id,
        which is the receiver's source id.
        """
        if receiver.source_id is None:
            return None
        return {(self.source_domain, receiver.source_id)}

    async def async_deliver(
        self, hass: HomeAssistant, receiver: Receiver, notification: Mapping[str, Any]
    ) -> list[str]:
        """Show a toast through the TV's ``notify.<title>`` action."""
        return await async_deliver_webostv(hass, receiver, notification)


class MusicAssistantReceiverType(DeviceReceiverType):
    """One receiver per Music Assistant player."""

    type_id = RECEIVER_TYPE_MUSIC_ASSISTANT
    name = "Music Assistant"
    source_domain = "music_assistant"
    # Not implemented yet (no delivery), so not offered as a discovery.
    discoverable = False


BUILTIN_RECEIVER_TYPES: tuple[type[ReceiverType], ...] = (
    MobileAppReceiverType,
    AlexaMediaReceiverType,
    PersistentNotificationReceiverType,
    PushoverReceiverType,
    WebOSTVReceiverType,
    MusicAssistantReceiverType,
)


def register_builtin_receiver_types() -> None:
    """Register the built-in types that are not registered yet."""
    for type_class in BUILTIN_RECEIVER_TYPES:
        if get_receiver_type(type_class.type_id) is None:
            register_receiver_type(type_class())
