# Notification content

The content of a notification is the `message`, an optional `title`, and
the fields below. See [the action](services.md) for the target fields.

## Message types

`message` is a list of items, each with a `type` and its `content`. The
type is **Text Display** (`text`) for receivers that show text, or
**Text-to-speech** (`tts`) for receivers that speak. A list reads badly when
spoken, so give each its own wording:

```yaml
action: notify.com_system
data:
  message:
    - type: text
      content: "Shopping: milk, eggs, bread"
    - type: tts
      content: You need milk, eggs and bread
  receivers:
    active_choice: All Areas
    All Areas: true
```

- Give one type to reach only the receivers that take it. A receiver whose
  types are not in the message is **skipped** (reason "No message content
  applies to this receiver type"), not failed.
- A plain string (`message: Hello`) is used for every type, so existing
  calls keep working.
- Each type may be given once. The type id or its label is accepted, in any
  case.

| Type | Message types taken |
| --- | --- |
| Mobile app, Pushover, webOS TV, persistent notification | `text` |
| [Alexa Media Player](receivers/alexa-media-player.md) | `tts`, else `text` |
| [Script](receivers/custom.md) | Both |

A script receives `message` (its first matching type) and `messages`, an
object with every type given. The mobile app can also speak a message, but
through a different mechanism that is not used yet.

## Common content

- `message` (required) is supported by every receiver type.
- `title` is optional. A type with no title concept drops it, with a
  warning.

## Priority and image

Two typed fields are validated by the action:

- `priority` is Low, Normal (the default), High or Critical. In YAML use
  `low`, `normal`, `high` or `critical`; the case does not matter. Each
  receiver type maps it to its own mechanism, described in its page.
- `image` is a choice of **Entity** (the form's first choice) or **URL**.
  An entity is an `image` or `camera` entity, sent as its current picture
  path (with its access token). A URL is an http(s) URL, a `/local/...`
  path or a media source ID (`media-source://...`). In YAML give the plain
  string (a URL or an entity id) or the form's `{active_choice: Entity, Entity: camera.door}`.

How each type handles them:

| Type | `priority` | `image` |
| --- | --- | --- |
| [Mobile app](receivers/mobile-app.md) | Mapped | `data.image` |
| [Pushover](receivers/pushover.md) | -1, 1 or 2 | Attachment (local file, not an entity) |
| [webOS TV](receivers/webostv.md) | No | No (use `data.icon`) |
| [Alexa Media Player](receivers/alexa-media-player.md) | No | No |
| [Persistent notification](receivers/persistent-notification.md) | No | No |
| [Script](receivers/custom.md) | Passed | Passed |

## Mobile app fields

Four typed fields are for mobile app notifications; `tag` is also
supported by persistent notifications. A receiver type that does not support
a field drops it with a warning.

- `click_action`: a URL or Home Assistant path (such as `/lovelace/cameras`)
  opened when the notification is tapped.
- `actions`: buttons, each with an `id` and a `label` (the button text), and optionally
  a `uri` to open instead of firing an event. Pressing one fires
  [`com_system_action`](receivers/mobile-app.md#actions-and-responses).
- `tag`: notifications with the same tag replace each other. Mobile apps
  can also use it to clear a notification. The
  [persistent notification](receivers/persistent-notification.md) receiver
  supports it too.
- `car_ui`: show the notification in Android Auto.

They are sent to the app as `clickAction` (and `url` for iOS), `actions`,
`tag` and `car_ui`; see [mobile app](receivers/mobile-app.md). A channel can
default any of them.

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

The **Test** page of the [panel](ui.md#test) builds its form from the
action, so it offers priority, image and `data` as well as the targets, and
shows any warnings about dropped content in the result.
