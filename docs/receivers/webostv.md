# webOS TV receiver

## Integration

Shows a notification as a toast on an LG TV, using Home Assistant's
[webOS TV](https://www.home-assistant.io/integrations/webostv/)
integration. One receiver is offered for each webOS TV config entry.

## Features

- The receiver's entities are placed on the TV's own device. Its area is the
  area of that device, so area targets reach it once the TV has an area (see
  [areas](../next-steps/areas.md)).
- A TV is a shared device: it has no person, so person targets never reach
  it (see [person](../next-steps/person.md)).
- A TV that is off is not an error: the notification is `skipped` with the
  reason `Device is off`, and is not queued.

## Notification parameters

| Parameter | Supported | Mapping |
| --- | --- | --- |
| `message` | Yes | `message` |
| `title` | No | Dropped, with a warning |
| `priority` | No | Dropped, with a warning |
| `image` | No | Dropped, with a warning; use `data.icon` |
| Other fields | No | Dropped, with a warning |

`data` is the `webostv` block. Other keys are dropped with a warning.

| Key | Description |
| --- | --- |
| `icon` | Path or URL of an icon shown in the toast |

```yaml
action: notify.com_system
data:
  message: Dinner is ready
  receivers:
    active_choice: Select
    Select:
      entity_id: notification_receiver.living_room_tv
  data:
    webostv:
      icon: /local/dinner.png
```

## Other information

Delivery calls the integration's `notify.<TV name>` action, named from the
config entry's title (for example `notify.living_room_tv`). If that action
does not exist (the TV was removed, or the integration is not loaded) the
delivery fails for that receiver only, with the reason in the result.

Whether the TV is off is decided from the state of its media player, and
also when the notify action fails after the TV went off. Other errors from
the action are `failed`. Older versions of the webOS TV integration only log
an error when the TV is unreachable, and are recorded as delivered.

The panel shows a TV in that state with a **Device off** status, and does
not count it in the available receivers on the dashboard. The receiver is
not unavailable, and its enabled switch still works.
