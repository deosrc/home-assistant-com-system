# webOS TV receiver

A webOS TV receiver shows a notification as a toast on an LG TV set up with
the Home Assistant webOS TV integration. Com System offers one receiver for
each webOS TV config entry (see
[automatic detection](README.md#automatic-detection)).

## Setup

Choose **Add** on the discovery under **Settings > Devices & services**. The
receiver's entities are placed on the TV's own device.

A TV is a shared device, so it has no person: **Configure** has no people
option and person targets never reach it. Its area is the area of the TV's
device in Home Assistant, so area targets reach it once the TV has an area.
To change the area, change it on the TV's device. See
[Receivers](README.md#people-and-areas) and [Targets](../targets.md).

## Supported content

| Content | Supported |
| --- | --- |
| `message` | Yes |
| `title` | No: dropped, with a warning in the result |
| `priority` | No: dropped, with a warning |
| `image` | No: dropped, with a warning (use `data.icon`) |
| `data.icon` | Yes: path or URL of an icon shown in the toast |

`data` is the `webostv` block, for example `data: {webostv: {icon: ...}}`.
Other keys are dropped with a warning. See [content](../content.md).

## Behaviour

Delivery calls the integration's `notify.<TV name>` action, named from the
config entry's title (for example `notify.living_room_tv`), with the message
and, when given, `data.icon`. If that action does not exist (the TV was
removed, or the integration is not loaded) the delivery fails for that
receiver only, with the reason in the result.

A TV that is off or unavailable is expected, so it is not an error: the
result is `skipped` with the reason `Device is off`. This is decided from
the state of the TV's media player, and also when the notify action fails
after the TV went off. The notification is not queued: it is lost. Other
errors from the action are `failed`. Older versions of the webOS TV
integration only log an error when the TV is unreachable, and are recorded
as delivered.

## Example

```yaml
action: notify.com_system
data:
  message: Dinner is ready
  receivers:
    active_choice: Select
    Select:
      entity_id: notification_receiver.living_room_tv
```
