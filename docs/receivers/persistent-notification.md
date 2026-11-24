# Persistent notification receiver

## Integration

Posts to the notification area in the Home Assistant sidebar, using the
built-in [Persistent Notification](https://www.home-assistant.io/integrations/persistent_notification/)
integration.

## Features

- Every user sees the same notifications, so the receiver is not tied to a
  person and has no push behaviour. It cannot have a person, so person
  targets never reach it.
- It starts with no area, so it is only used when named in the `receivers`
  target. Give its device an area and area targets reach it like any other
  receiver. See [areas](../next-steps/areas.md) and
  [targets](../targets.md).
- Commands: [clear notification](../commands.md#clear-a-notification).

## Notification parameters

| Parameter | Supported | Mapping |
| --- | --- | --- |
| `message` | Yes | `message` |
| `title` | Yes | `title` |
| `tag` | Yes | Notification ID; the same tag replaces the old one |
| `priority`, `image`, others | No | Dropped, with a warning |
| `data` | No | Dropped, with a warning |

There are no receiver-specific `data` options.

```yaml
action: notify.com_system
data:
  title: Backup failed
  message: The nightly backup did not finish.
  receivers:
    active_choice: Select
    Select:
      entity_id: notification_receiver.persistent_notification
```

## Other information

Delivery calls `persistent_notification.create`.

If no `tag` is specified, each notification creates its own entry. With a `tag`
the notification's ID is set to `com_system_tag_<tag>`. The next notification
with the same tag replaces the previous one.

Only notifications sent with a tag can be removed with the
[clear notification command](../commands.md#clear-a-notification);
dismiss others in the Home Assistant UI as normal.
