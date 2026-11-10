"""Target resolution: which receivers a notification goes to."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from homeassistant.core import HomeAssistant

from .const import DATA_ENTITIES, DATA_REGISTRY, DOMAIN
from .receiver import Receiver


@dataclass(frozen=True, slots=True)
class ResolvedTargets:
    """The outcome of resolving targets.

    ``receivers`` are the enabled receivers to notify. ``skipped`` are
    receivers that matched but are disabled; delivery records them as
    skipped. Each list is ordered by receiver name, then entry id.
    """

    receivers: tuple[Receiver, ...]
    skipped: tuple[Receiver, ...]


def is_enabled(hass: HomeAssistant, receiver: Receiver) -> bool:
    """Return whether the receiver's enabled switch is on.

    A receiver whose switch is not loaded cannot deliver, so it is not
    enabled.
    """
    entities = hass.data[DOMAIN][DATA_ENTITIES].get(receiver.entry_id, {})
    switch = entities.get("enabled")
    return switch is not None and switch.is_on is True


def resolve_targets(
    hass: HomeAssistant,
    *,
    people: Collection[str] | None = None,
    all_people: bool = False,
    areas: Collection[str] | None = None,
    all_areas: bool = False,
    receivers: Collection[str] | None = None,
) -> ResolvedTargets:
    """Resolve targets to receivers.

    ``people`` are ``person.*`` entity ids, ``areas`` are area ids and
    ``receivers`` are receiver config entry ids. ``all_people`` matches every
    receiver that has a person, whoever it is, and ``all_areas`` every
    receiver that has an area. The result is the union of
    the receivers that match any of them. With no targets at all, every
    receiver associated with any person or area matches. Shared receivers
    (no person) are never matched by person; a receiver without an area is
    never matched by area, so the persistent notification receiver, which
    has neither until you give it one, is only reached when named. Disabled
    receivers are returned as skipped, however they were matched. Unknown ids
    match nothing.
    """
    registry = hass.data[DOMAIN][DATA_REGISTRY]
    people_set = set(people or ())
    area_set = set(areas or ())
    named = set(receivers or ())
    default = not (people_set or all_people or area_set or all_areas or named)

    matched: list[Receiver] = []
    for receiver in registry.all():
        receiver_people = registry.people_of(receiver)
        receiver_areas = registry.areas_of(receiver)
        if receiver.entry_id in named:
            matched.append(receiver)
        elif default:
            if receiver_people or receiver_areas:
                matched.append(receiver)
        elif (
            (all_people and receiver_people)
            or (all_areas and receiver_areas)
            or people_set.intersection(receiver_people)
            or area_set.intersection(receiver_areas)
        ):
            matched.append(receiver)

    matched.sort(key=lambda r: (r.name.casefold(), r.entry_id))
    return ResolvedTargets(
        receivers=tuple(r for r in matched if is_enabled(hass, r)),
        skipped=tuple(r for r in matched if not is_enabled(hass, r)),
    )
