# Mobile app receiver

## Integration

Sends notifications to one device running the Home Assistant companion app,
using Home Assistant's [Mobile
App](https://www.home-assistant.io/integrations/mobile_app/) integration (see
also the [companion app
documentation](https://companion.home-assistant.io/docs/notifications/notifications-basic/)).
Com System offers one receiver for each registered device (see [automatic
detection](README.md#automatic-detection)).

## Features

- Works on Android and iOS; keys for the other platform are ignored by the
  app.
- Buttons on the notification, with [responses](#actions-and-responses)
  that fire events and start automations.
- [Channels](../next-steps/channels.md): the channel name is sent as the
  Android notification channel.
- Commands: [clear notification](../commands.md#clear-a-notification).
- The person is found automatically, and the device can be personal or
  shared (see [person](../next-steps/person.md#mobile-app)). The area is the
  area of the device in Home Assistant (see
  [areas](../next-steps/areas.md)).

## Notification parameters

| Parameter | Supported | Mapping |
| --- | --- | --- |
| `message`, `title` | Yes | `message`, `title` |
| `priority` | Yes | `data` keys, see below |
| `image` | Yes | `data.image` |
| `click_action` | Yes | `clickAction` (Android) and `url` (iOS) |
| `actions` | Yes | `actions`, with `id` as `action` and `label` as `title` |
| `tag` | Yes | `tag` |
| `car_ui` | Yes | `car_ui: true` (nothing when off) |
| `data` | Yes | The `mobile_app` block, any key |

`priority` is mapped to the companion app's keys; each platform ignores the
other's:

- `low`: Android `importance: low`; iOS `passive`.
- `normal`: nothing.
- `high`: Android `importance: high`, `ttl: 0`, `priority: high`; iOS
  `time-sensitive`.
- `critical`: Android `importance: max`, `ttl: 0`, `priority: high`; iOS
  `critical` with a critical sound at full volume.

`image` is passed as `data.image`; an `image` or `camera` entity becomes its
current picture path, and a media source ID is resolved to a URL first (if
it cannot be, the image is dropped with a warning). The `mobile_app`
block of `data` is merged over these, so it can override them and add
keys such as `actions`, `tag` or `channel`:

```yaml
action: notify.com_system
data:
  message: Someone is at the door
  priority: high
  image: /local/doorbell.jpg
  data:
    mobile_app:
      tag: door
```

The iOS `url` key is from the companion app documentation and has not been
checked on a device.

## Other information

### Delivery

A notification is delivered by calling the device's own
`notify.mobile_app_<device name>` action with the message and, when given,
the title. If that action does not exist (for example the device has no push
support or was removed) the delivery fails for that receiver only, with the
reason in the result.

### Actions and responses

Buttons on the notification are the `actions` field: a list of objects
with an `id`, a `label` (the button text) and optionally a `uri` (other app
keys such as `behavior` are passed through). In the form it is a list
editor. Actions given in the `mobile_app` data block use the app's own
`action` and `title` keys.

```yaml
action: notify.com_system
data:
  message: Someone is at the door
  channel: notification_channel.doorbell
  actions:
    - id: OPEN
      label: Open the gate
    - id: IGNORE
      label: Ignore
```

Each notification has an ID, returned as `id` in the action's response. Com
System sends each action to the app with the notification and receiver
encoded in its ID, because the app returns only that ID when a button is
pressed. When someone presses an action, Com System fires a
`com_system_action` event:

| Key | Value |
| --- | --- |
| `notification_id` | The `id` of the notification |
| `tag` | The notification's `tag`, none if it had no tag |
| `receiver_id` | The receiver's config entry ID |
| `receiver` | The receiver's name |
| `person` | The device's person (`person.*`), none for a shared device |
| `action` | The `id` of the action that was pressed |
| `reply_text` | The text typed, for an action that asks for a reply |

```yaml
triggers:
  - trigger: event
    event_type: com_system_action
    event_data:
      action: OPEN
```

To start an automation from a response, use the
[action received trigger](../triggers.md).

The response is also stored with the notification in
[history](../next-steps/dashboard.md#history) and shown under Recent. If the
notification has already left history the event is still fired. Actions with a
`uri` open it and send no response. Responses to notifications that Com System
did not send are ignored. Automations that listen to
`mobile_app_notification_action` directly see the encoded ID, so use
`com_system_action`, which has the original one.

In the [testing tool](../next-steps/dashboard.md#test), enter the actions in the
`data` field like any other receiver content; the form has no action editor of
its own.

### Which person a device belongs to

See [receiver person](../next-steps/person.md#mobile-app), including
[personal or shared](../next-steps/person.md#personal-or-shared) devices.
