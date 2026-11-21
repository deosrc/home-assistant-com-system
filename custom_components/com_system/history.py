"""The notification history: a capped record of what was sent and to whom.

History lives in Home Assistant's JSON ``Store``. It is created once in
``async_setup`` and the limits (count and age) are read from the hub entry's
options each time they are needed, so changing them reloads nothing.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .conditions import REASON_CONDITION_ERROR, REASON_CONDITIONS
from .const import (
    CONF_ENTRY_TYPE,
    CONF_HISTORY_MAX_AGE_DAYS,
    CONF_HISTORY_MAX_COUNT,
    DEFAULT_HISTORY_MAX_AGE_DAYS,
    DEFAULT_HISTORY_MAX_COUNT,
    DOMAIN,
    ENTRY_TYPE_HUB,
    RESULT_FAILED,
    RESULT_SKIPPED,
)

if TYPE_CHECKING:
    from .dispatcher import ReceiverResult

STORAGE_KEY = f"{DOMAIN}.history"
STORAGE_VERSION = 1
SAVE_DELAY_SECONDS = 10

# The notification fields kept in history.
CONTENT_KEYS = (
    "title",
    "message",
    "messages",
    "priority",
    "image",
    "click_action",
    "actions",
    "tag",
    "car_ui",
    "data",
    "channel",
)


class NotificationHistory:
    """Newest-first list of notification records, capped by count and age."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Create the history; it loads from storage on first use."""
        self._hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._records: list[dict[str, Any]] | None = None

    def limits(self) -> tuple[int, int]:
        """Return ``(max_count, max_age_days)`` from the hub's options."""
        options: Mapping[str, Any] = {}
        for entry in self._hass.config_entries.async_entries(DOMAIN):
            if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_HUB:
                options = entry.options
                break
        return (
            int(options.get(CONF_HISTORY_MAX_COUNT, DEFAULT_HISTORY_MAX_COUNT)),
            int(options.get(CONF_HISTORY_MAX_AGE_DAYS, DEFAULT_HISTORY_MAX_AGE_DAYS)),
        )

    async def async_load(self) -> None:
        """Load the stored records (once)."""
        if self._records is not None:
            return
        data = await self._store.async_load()
        self._records = list((data or {}).get("records", []))
        self._prune()

    def _prune(self, now: datetime | None = None) -> None:
        """Drop records over the count limit or older than the age limit."""
        assert self._records is not None
        max_count, max_age_days = self.limits()
        cutoff = (now or dt_util.utcnow()) - timedelta(days=max_age_days)
        kept = [
            r
            for r in self._records
            if (parsed := dt_util.parse_datetime(r["time"])) is not None
            and parsed >= cutoff
        ]
        self._records = kept[: max(max_count, 0)]

    def _schedule_save(self) -> None:
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY_SECONDS)

    def _data_to_save(self) -> dict[str, Any]:
        return {"records": self._records or []}

    async def async_record(
        self,
        notification: Mapping[str, Any],
        results: list[ReceiverResult],
    ) -> dict[str, Any]:
        """Record a notification with every receiver's result and warnings."""
        await self.async_load()
        assert self._records is not None
        record = {
            "id": notification.get("id") or uuid.uuid4().hex,
            "time": dt_util.utcnow().isoformat(),
            "notification": {
                key: notification[key] for key in CONTENT_KEYS if key in notification
            },
            "results": [r.as_dict() for r in results],
            "responses": [],
        }
        self._records.insert(0, record)
        self._prune()
        self._schedule_save()
        return record

    async def async_add_response(
        self, notification_id: str, response: Mapping[str, Any]
    ) -> bool:
        """Store a response to a notification's action.

        Returns False when the notification is no longer in history (the
        response is then only fired as an event).
        """
        await self.async_load()
        assert self._records is not None
        for record in self._records:
            if record["id"] == notification_id:
                record.setdefault("responses", []).append(dict(response))
                self._schedule_save()
                return True
        return False

    async def async_list(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Return the records, newest first (pruned by the current limits)."""
        await self.async_load()
        self._prune()
        assert self._records is not None
        return list(self._records if limit is None else self._records[:limit])

    async def async_last_attempt(self, entry_id: str) -> dict[str, Any] | None:
        """Return a receiver's latest result with its notification and time."""
        for record in await self.async_list():
            for result in record["results"]:
                if result["entry_id"] == entry_id:
                    return {
                        **result,
                        "time": record["time"],
                        "notification": record["notification"],
                    }
        return None

    async def async_stats(self, now: datetime | None = None) -> dict[str, Any]:
        """Summarise the history for the dashboard.

        Rates are ``None`` when there is nothing to base them on. While the
        history is under its count limit it covers the whole age limit, so
        ``rate`` is notifications per day over that period (``rate_unit``
        ``"day"``). Once at the count limit the history covers only part of
        that period, so ``rate`` is per hour over the whole hours since the
        first hour boundary after the oldest record (``"hour"``); with no
        whole hour yet ``rate`` is ``None`` and ``rate_unit`` is ``"hour"``.
        A notification succeeded when none of its receivers failed (all
        success or skipped). ``stopped_by_condition`` counts notifications
        where a receiver was skipped by its conditions.
        """
        records = await self.async_list()
        now = now or dt_util.utcnow()
        max_count, max_age_days = self.limits()
        count = len(records)
        results = [r for rec in records for r in rec["results"]]
        notifications_ok = sum(
            all(r["result"] != RESULT_FAILED for r in rec["results"]) for rec in records
        )
        receivers_ok = sum(r["result"] != RESULT_FAILED for r in results)
        stopped = sum(
            any(_stopped_by_condition(r) for r in rec["results"]) for rec in records
        )
        rate: float | None = None
        rate_unit = "day"
        if count and count >= max_count:
            rate_unit = "hour"
            oldest = dt_util.parse_datetime(records[-1]["time"])
            if oldest is not None:
                start = oldest.replace(minute=0, second=0, microsecond=0)
                if start < oldest:
                    start += timedelta(hours=1)
                hours = int((now - start) / timedelta(hours=1))
                if hours >= 1:
                    in_window = sum(
                        1
                        for rec in records
                        if (t := dt_util.parse_datetime(rec["time"])) is not None
                        and t >= start
                    )
                    rate = in_window / hours
        elif max_age_days > 0:
            rate = count / max_age_days
        return {
            "notifications": count,
            "rate": rate,
            "rate_unit": rate_unit,
            "notification_success_rate": notifications_ok / count if count else None,
            "receiver_success_rate": receivers_ok / len(results) if results else None,
            "stopped_by_condition_rate": stopped / count if count else None,
        }

    async def async_clear(self) -> None:
        """Remove every record."""
        await self.async_load()
        self._records = []
        await self._store.async_save(self._data_to_save())


def _stopped_by_condition(result: Mapping[str, Any]) -> bool:
    """Whether a receiver's result was skipped by its conditions."""
    reason = result.get("reason") or ""
    return result["result"] == RESULT_SKIPPED and reason.startswith(
        (REASON_CONDITIONS, REASON_CONDITION_ERROR)
    )
