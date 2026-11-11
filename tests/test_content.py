"""Tests for content parameters, capabilities and per-type delivery."""

from pathlib import Path

import pytest
import voluptuous as vol
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.com_system.const import (
    CONF_ENTRY_TYPE,
    CONF_NAME,
    CONF_PEOPLE,
    CONF_RECEIVER_TYPE,
    CONF_SOURCE_ID,
    DOMAIN,
    ENTRY_TYPE_HUB,
    ENTRY_TYPE_RECEIVER,
    RECEIVER_TYPE_ALEXA_MEDIA,
    RECEIVER_TYPE_MOBILE_APP,
    RECEIVER_TYPE_PERSISTENT_NOTIFICATION,
    RECEIVER_TYPE_PUSHOVER,
    RECEIVER_TYPE_WEBOSTV,
)
from custom_components.com_system.content import (
    apply_capabilities,
    local_image_path,
    merge,
    validate_data,
    validate_image,
    validate_priority,
)
from custom_components.com_system.receiver_type import (
    CustomReceiverType,
    ReceiverType,
    get_receiver_type,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component


class _Type(ReceiverType):
    type_id = "t"
    name = "T"
    capabilities = frozenset({"priority", "data.a"})


def test_validators() -> None:
    """Priority, image and data accept only documented forms."""
    assert validate_priority("critical") == "critical"
    with pytest.raises(vol.Invalid):
        validate_priority("urgent")
    for image in (
        "https://x/y.png",
        "/local/a.png",
        "media-source://media_source/local/a.png",
    ):
        assert validate_image(image) == image
    for image in ("ftp://x", "a.png", "/local/", "/config/a.png"):
        with pytest.raises(vol.Invalid):
            validate_image(image)
    assert validate_data({"pushover": {"sound": "x"}}) == {"pushover": {"sound": "x"}}
    with pytest.raises(vol.Invalid):
        validate_data({"pushover": "x"})
    with pytest.raises(vol.Invalid):
        validate_data(["x"])


def test_merge_is_deep() -> None:
    """Objects merge, other values replace."""
    assert merge({"push": {"a": 1, "b": 2}, "x": 1}, {"push": {"b": 3}, "x": 2}) == {
        "push": {"a": 1, "b": 3},
        "x": 2,
    }


def test_apply_capabilities_drops_with_warnings() -> None:
    """Unsupported fields and keys are dropped; the type's block is passed."""
    content, warnings = apply_capabilities(
        _Type(),
        {
            "message": "m",
            "title": "t",
            "image": "/local/a.png",
            "priority": "high",
            "data": {"t": {"a": 1, "b": 2}, "other": {"x": 1}},
        },
    )
    assert content == {"message": "m", "priority": "high", "data": {"a": 1}}
    assert warnings == [
        "The title is not supported by T and was dropped",
        "The image is not supported by T and was dropped",
        "The data key b is not supported by T and was dropped",
    ]


def test_normal_priority_and_other_blocks_are_not_warnings() -> None:
    """Normal is the default; another type's block is simply not for us."""

    class Plain(ReceiverType):
        type_id = "p"
        name = "P"

    content, warnings = apply_capabilities(
        Plain(), {"message": "m", "priority": "normal", "data": {"x": {"a": 1}}}
    )
    assert content == {"message": "m"}
    assert warnings == []


def test_custom_type_accepts_everything() -> None:
    """Scripts get all content, with data as their own block."""
    content, warnings = apply_capabilities(
        CustomReceiverType(),
        {"message": "m", "image": "/local/a", "data": {"custom": {"k": 1}, "x": {}}},
    )
    assert content == {"message": "m", "image": "/local/a", "data": {"k": 1}}
    assert warnings == []


async def test_declared_capabilities(hass: HomeAssistant) -> None:
    """What each built-in type supports."""
    await _setup(hass)

    def caps(type_id):
        return get_receiver_type(type_id).capabilities

    assert caps(RECEIVER_TYPE_MOBILE_APP) == {"title", "priority", "image", "data"}
    assert caps(RECEIVER_TYPE_ALEXA_MEDIA) == {"title"}
    assert caps(RECEIVER_TYPE_PERSISTENT_NOTIFICATION) == {"title"}
    assert caps(RECEIVER_TYPE_WEBOSTV) == {"data.icon"}
    assert {"title", "priority", "image", "data.sound", "data.attachment"} <= caps(
        RECEIVER_TYPE_PUSHOVER
    )


async def _setup(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN, data={CONF_ENTRY_TYPE: ENTRY_TYPE_HUB}).add_to_hass(
        hass
    )
    assert await async_setup_component(hass, DOMAIN, {})


def _record(hass: HomeAssistant, domain: str, service: str) -> list[ServiceCall]:
    calls: list[ServiceCall] = []

    async def handler(call: ServiceCall) -> None:
        calls.append(call)

    hass.services.async_register(domain, service, handler)
    return calls


async def _receiver(hass, type_id, source_id, name):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=name,
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_RECEIVER,
            CONF_RECEIVER_TYPE: type_id,
            CONF_SOURCE_ID: source_id,
            CONF_NAME: name,
        },
        options={CONF_PEOPLE: ["person.a"]},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _send(hass, **data):
    """Send to every receiver (named by entity, as none has an area)."""
    entities = [s.entity_id for s in hass.states.async_all("notification_receiver")]
    return await hass.services.async_call(
        "notify",
        "com_system",
        {
            "receivers": {"active_choice": "Select", "Select": {"entity_id": entities}},
            **data,
        },
        blocking=True,
        return_response=True,
    )


async def test_persistent_notification_drops_rich_content(hass: HomeAssistant) -> None:
    """Content the type does not support is dropped; delivery succeeds."""
    await _setup(hass)
    calls = _record(hass, "persistent_notification", "create")
    await _receiver(
        hass, RECEIVER_TYPE_PERSISTENT_NOTIFICATION, "persistent_notification", "PN"
    )

    response = await _send(
        hass,
        message="m",
        title="t",
        priority="high",
        image="/local/a.png",
        data={"mobile_app": {"actions": []}},
    )

    assert response["counts"]["delivered"] == 1
    assert response["results"][0]["warnings"] == [
        "The priority is not supported by Persistent notification and was dropped",
        "The image is not supported by Persistent notification and was dropped",
    ]
    assert calls[0].data == {"message": "m", "title": "t"}
    state = hass.states.get("notification_receiver.pn")
    assert state.attributes["priority"] == "high"
    assert state.attributes["warnings"] == response["results"][0]["warnings"]


async def test_webostv_icon_from_its_block(hass: HomeAssistant) -> None:
    """Only the webostv data block's icon reaches the TV."""
    await _setup(hass)
    source = MockConfigEntry(domain="webostv", title="TV", unique_id="tv1")
    source.add_to_hass(hass)
    calls = _record(hass, "notify", "tv")
    await _receiver(hass, RECEIVER_TYPE_WEBOSTV, "tv1", "TV")

    response = await _send(
        hass,
        message="m",
        title="t",
        data={"webostv": {"icon": "/a.png", "x": 1}, "pushover": {"sound": "s"}},
    )

    assert calls[0].data == {"message": "m", "data": {"icon": "/a.png"}}
    assert response["results"][0]["warnings"] == [
        "The title is not supported by webOS TV and was dropped",
        "The data key x is not supported by webOS TV and was dropped",
    ]


async def _mobile(hass):
    await _setup(hass)
    source = MockConfigEntry(
        domain="mobile_app",
        data={"device_id": "d1", "device_name": "Phone", "user_id": "u"},
    )
    source.add_to_hass(hass)
    calls = _record(hass, "notify", "mobile_app_phone")
    await _receiver(hass, RECEIVER_TYPE_MOBILE_APP, "d1", "Phone")
    return calls


async def test_mobile_app_maps_priority_image_and_data(hass: HomeAssistant) -> None:
    """Priority and image map to data keys; the block wins."""
    calls = await _mobile(hass)

    await _send(
        hass,
        message="m",
        priority="high",
        image="/local/a.png",
        data={"mobile_app": {"tag": "t", "ttl": 5, "push": {"badge": 1}}},
    )

    assert calls[0].data == {
        "message": "m",
        "data": {
            "importance": "high",
            "ttl": 5,
            "priority": "high",
            "push": {"interruption-level": "time-sensitive", "badge": 1},
            "image": "/local/a.png",
            "tag": "t",
        },
    }


async def test_mobile_app_critical_and_plain(hass: HomeAssistant) -> None:
    """Critical sets the critical alert; normal adds nothing."""
    calls = await _mobile(hass)

    await _send(hass, message="a", priority="critical")
    await _send(hass, message="b", priority="normal")

    assert calls[0].data["data"]["push"]["interruption-level"] == "critical"
    assert calls[0].data["data"]["push"]["sound"]["critical"] == 1
    assert calls[1].data == {"message": "b"}


async def test_mobile_app_unresolvable_media_source_warns(hass: HomeAssistant) -> None:
    """An image that cannot be resolved is dropped with a warning."""
    calls = await _mobile(hass)

    response = await _send(
        hass, message="m", image="media-source://media_source/local/a.png"
    )

    assert calls[0].data == {"message": "m"}
    assert response["counts"]["delivered"] == 1
    [warning] = response["results"][0]["warnings"]
    assert warning.startswith("The image was dropped")


async def _pushover(hass):
    await _setup(hass)
    source = MockConfigEntry(
        domain="pushover", title="Pushover", unique_id="u1", data={"name": "pushover"}
    )
    source.add_to_hass(hass)
    calls = _record(hass, "notify", "pushover")
    await _receiver(hass, RECEIVER_TYPE_PUSHOVER, "u1:phone", "Phone")
    return calls


async def test_pushover_maps_priority_and_data(hass: HomeAssistant) -> None:
    """Priority maps to -1/1/2; critical adds retry and expire."""
    calls = await _pushover(hass)

    await _send(hass, message="a", priority="low")
    await _send(
        hass,
        message="b",
        priority="critical",
        data={"pushover": {"sound": "siren", "retry": 30}},
    )
    await _send(hass, message="c", priority="normal")

    assert calls[0].data["data"] == {"priority": -1}
    assert calls[1].data["data"] == {
        "priority": 2,
        "retry": 30,
        "expire": 3600,
        "sound": "siren",
    }
    assert "data" not in calls[2].data


async def test_pushover_image_must_be_allowed_local_file(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """A /local/ file in an allowed folder is attached; others warn."""
    calls = await _pushover(hass)
    www = Path(hass.config.path("www"))
    www.mkdir(parents=True, exist_ok=True)
    (www / "a.png").write_bytes(b"x")
    hass.config.allowlist_external_dirs = {str(www)}

    ok = await _send(hass, message="a", image="/local/a.png")
    missing = await _send(hass, message="b", image="/local/none.png")
    url = await _send(hass, message="c", image="https://x/y.png")

    assert calls[0].data["data"] == {"attachment": str(www / "a.png")}
    assert ok["results"][0]["warnings"] == []
    for response in (missing, url):
        assert response["results"][0]["warnings"][0].startswith("The image was dropped")
    assert "data" not in calls[1].data
    assert "data" not in calls[2].data


def test_local_image_path_rules(hass: HomeAssistant) -> None:
    """Paths outside the folder or the allowlist are refused."""
    www = hass.config.path("www")
    hass.config.allowlist_external_dirs = {www}
    assert local_image_path(hass, "/local/a/b.png") == str(Path(www) / "a" / "b.png")
    with pytest.raises(HomeAssistantError, match="outside"):
        local_image_path(hass, "/local/../secrets.yaml")
    hass.config.allowlist_external_dirs = set()
    with pytest.raises(HomeAssistantError, match="allowlist"):
        local_image_path(hass, "/local/a.png")
    with pytest.raises(HomeAssistantError, match="URL"):
        local_image_path(hass, "https://x/y.png")
    hass.config.media_dirs = {"local": "/media"}
    hass.config.allowlist_external_dirs = {"/media"}
    assert (
        local_image_path(hass, "media-source://media_source/local/p/a.png")
        == "/media/p/a.png"
    )
    with pytest.raises(HomeAssistantError, match="not a local media file"):
        local_image_path(hass, "media-source://media_source/other/a.png")


async def test_alexa_drops_everything_but_title(hass: HomeAssistant) -> None:
    """Alexa speaks the message; priority and image are dropped."""
    await _setup(hass)
    MockConfigEntry(domain="alexa_media").add_to_hass(hass)
    calls = _record(hass, "notify", "alexa_media")
    await _receiver(hass, RECEIVER_TYPE_ALEXA_MEDIA, "echo1", "Echo")

    response = await _send(hass, message="m", priority="high", image="/local/a.png")

    assert calls[0].data == {
        "message": "m",
        "target": ["echo1"],
        "data": {"type": "announce"},
    }
    assert len(response["results"][0]["warnings"]) == 2
