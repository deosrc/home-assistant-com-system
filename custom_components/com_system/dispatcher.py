"""The dispatcher: delivers a notification to resolved receivers."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    DATA_ENTITIES,
    DATA_HISTORY,
    DOMAIN,
    RESULT_DELIVERED,
    RESULT_FAILED,
    RESULT_SKIPPED,
)
from .receiver import Receiver
from .registry import ReceiverRegistry
from .targets import ResolvedTargets

_LOGGER = logging.getLogger(__name__)

REASON_DISABLED = "Receiver is disabled"
REASON_UNKNOWN_TYPE = "Receiver type is not available"
REASON_NOT_IMPLEMENTED = "Delivery is not implemented for this receiver type"


@dataclass(frozen=True, slots=True)
class ReceiverResult:
    """The outcome for one receiver."""

    receiver: Receiver
    type_name: str
    result: str
    reason: str | None = None
    warnings: list[str] = field(default_factory=list)
    # Why the receiver was included; see ``ResolvedTargets.reasons``.
    reasons: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """Return the result as response data."""
        return {
            "entry_id": self.receiver.entry_id,
            "name": self.receiver.name,
            "type": self.type_name,
            "result": self.result,
            "reason": self.reason,
            "warnings": list(self.warnings),
            "reasons": [dict(r) for r in self.reasons],
        }


def _record(
    hass: HomeAssistant,
    result: ReceiverResult,
    notification: Mapping[str, Any],
) -> None:
    """Record the attempt on the receiver's entity, if it is loaded."""
    entities = hass.data[DOMAIN][DATA_ENTITIES].get(result.receiver.entry_id, {})
    entity = entities.get("receiver")
    if entity is not None:
        entity.async_record_attempt(result.result, notification, result.warnings)


async def _deliver(
    hass: HomeAssistant,
    registry: ReceiverRegistry,
    receiver: Receiver,
    notification: Mapping[str, Any],
) -> ReceiverResult:
    """Deliver to one receiver. Never raises: failures become results."""
    receiver_type = registry.type_of(receiver)
    if receiver_type is None:
        return ReceiverResult(
            receiver, receiver.type_id, RESULT_FAILED, REASON_UNKNOWN_TYPE
        )
    try:
        warnings = await receiver_type.async_deliver(hass, receiver, notification)
    except NotImplementedError:
        _LOGGER.warning(
            "Delivery to %s failed: %s", receiver.name, REASON_NOT_IMPLEMENTED
        )
        return ReceiverResult(
            receiver, receiver_type.name, RESULT_FAILED, REASON_NOT_IMPLEMENTED
        )
    except Exception as err:
        _LOGGER.warning("Delivery to %s failed: %s", receiver.name, err)
        return ReceiverResult(
            receiver, receiver_type.name, RESULT_FAILED, str(err) or type(err).__name__
        )
    for warning in warnings or ():
        _LOGGER.warning("Notification for %s: %s", receiver.name, warning)
    return ReceiverResult(
        receiver, receiver_type.name, RESULT_DELIVERED, warnings=list(warnings or ())
    )


async def async_dispatch(
    hass: HomeAssistant,
    resolved: ResolvedTargets,
    notification: Mapping[str, Any],
) -> list[ReceiverResult]:
    """Deliver to every resolved receiver independently.

    Receivers are delivered to concurrently; one failing or raising never
    affects another. Skipped (disabled) receivers get a skipped result. Every
    attempt is recorded on the receiver's entity and in the history store.
    Results are ordered by
    receiver name, then entry id.
    """
    registry: ReceiverRegistry = hass.data[DOMAIN]["registry"]

    def type_name(receiver: Receiver) -> str:
        receiver_type = registry.type_of(receiver)
        return receiver_type.name if receiver_type else receiver.type_id

    delivered = await asyncio.gather(
        *(_deliver(hass, registry, r, notification) for r in resolved.receivers)
    )
    skipped = [
        ReceiverResult(r, type_name(r), RESULT_SKIPPED, REASON_DISABLED)
        for r in resolved.skipped
    ]
    results = sorted(
        [
            replace(r, reasons=list(resolved.reasons.get(r.receiver.entry_id, [])))
            for r in [*delivered, *skipped]
        ],
        key=lambda x: (x.receiver.name.casefold(), x.receiver.entry_id),
    )
    for result in results:
        _record(hass, result, notification)
    await hass.data[DOMAIN][DATA_HISTORY].async_record(notification, results)
    return results
