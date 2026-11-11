"""Target resolution: which receivers a notification goes to."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass, field

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
    # Why each receiver matched, by entry id: a list of ``{"kind", "id"}``
    # with kind ``person`` or ``area`` (the receiver's own person or area
    # that matched), ``everyone`` or ``all_areas`` (those choices matched it,
    # so no person or area is listed) or ``receiver`` (it was named). A
    # receiver can have several; ``id`` is absent for everyone and all_areas.
    reasons: dict[str, list[dict[str, str]]] = field(default_factory=dict)


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
    receiver that has an area. The result is the union of the receivers that
    match any of them. A group that is not given is not targeted, so with no
    targets at all nothing matches. A receiver with no person and no area is
    only matched when named. Disabled receivers are returned as skipped,
    however they were matched. Unknown ids match nothing.
    """
    registry = hass.data[DOMAIN][DATA_REGISTRY]
    people_set = set(people or ())
    area_set = set(areas or ())
    named = set(receivers or ())

    matched: list[Receiver] = []
    reasons: dict[str, list[dict[str, str]]] = {}
    for receiver in registry.all():
        receiver_people = registry.people_of(receiver)
        receiver_areas = registry.areas_of(receiver)
        why: list[dict[str, str]] = []
        if all_people and receiver_people:
            why.append({"kind": "everyone"})
        else:
            why += [
                {"kind": "person", "id": p} for p in receiver_people if p in people_set
            ]
        if all_areas and receiver_areas:
            why.append({"kind": "all_areas"})
        else:
            why += [
                {"kind": "area", "id": area}
                for area in receiver_areas
                if area in area_set
            ]
        if receiver.entry_id in named:
            why.append({"kind": "receiver", "id": receiver.entry_id})
        if why:
            matched.append(receiver)
            reasons[receiver.entry_id] = why

    matched.sort(key=lambda r: (r.name.casefold(), r.entry_id))
    return ResolvedTargets(
        receivers=tuple(r for r in matched if is_enabled(hass, r)),
        skipped=tuple(r for r in matched if not is_enabled(hass, r)),
        reasons=reasons,
    )
