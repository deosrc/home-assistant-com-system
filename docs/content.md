# Notification content

The content of a notification is the `message`, an optional `title`, and
the fields below. See [the action](services.md) for the target fields.

## Common content

- `message` (required) is supported by every receiver type.
- `title` is optional. A type with no title concept drops it, with a
  warning.

## Priority and image

Two typed fields are validated by the action:

- `priority` is `low`, `normal` (the default), `high` or `critical`. Each
  receiver type maps it to its own mechanism, described in its page.
- `image` is an http(s) URL, a `/local/...` path or a media source ID
  (`media-source://...`). Camera entities are not supported.

How each type handles them:

| Type | `priority` | `image` |
| --- | --- | --- |
| [Mobile app](receivers/mobile-app.md) | Mapped | `data.image` |
| [Pushover](receivers/pushover.md) | -1, 1 or 2 | Attachment (local file) |
| [webOS TV](receivers/webostv.md) | No | No (use `data.icon`) |
| [Alexa Media Player](receivers/alexa-media-player.md) | No | No |
| [Persistent notification](receivers/persistent-notification.md) | No | No |
| [Script](receivers/custom.md) | Passed | Passed |

## Receiver-specific data

Anything else goes in `data`, an object **keyed by receiver type**. The key
is the type's id: `mobile_app`, `pushover`, `webostv`, `alexa_media`,
`persistent_notification` or `custom` (scripts). Each receiver reads only
its own block, so one notification can carry settings for several types:

```yaml
action: notify.com_system
data:
  message: Washing finished
  priority: high
  people:
    active_choice: Everyone
    Everyone: true
  data:
    mobile_app:
      tag: laundry
    pushover:
      sound: bike
```

Each value must be an object. A block for a type that is not reached is
ignored without a warning. Within a block, a key the type does not support
is dropped with a warning.

## Capabilities and unsupported content

Every receiver type declares what it supports: `title`, `priority`,
`image`, `data` (any key of its block) and `data.<key>` (that key only).
Scripts accept anything. Content outside a type's capabilities is dropped
before delivery and the receiver is still notified with the rest. Delivery
is not a failure.

Each dropped item is a warning, such as
`The priority is not supported by webOS TV and was dropped`. Warnings are
logged, returned in the [action's response](services.md#response) and
recorded on the receiver's entity. A `priority` of `normal` is the default
and is never reported as dropped. Content a type supports but cannot use
(for example an image that is not a local file for Pushover) is a warning
too.

## Designing a notification

The **Test** page of the [panel](ui.md#test) shows the content options that
apply to the receivers the targets would reach: priority, image and one
data block per type, each listing which of the reached types would drop it.
