# Mobile app receivers

A mobile app receiver sends notifications to one device that runs the Home
Assistant companion app. Com System offers one receiver for each registered
device (see [automatic detection](README.md#automatic-detection)).

## Delivery

A notification is delivered by calling the device's own
`notify.mobile_app_<device name>` action with the message and, when given,
the title. If that action does not exist (for example the device has no push
support or was removed) the delivery fails for that receiver only, with the
reason in the result.

## Supported content

| Content | Supported |
| --- | --- |
| `message`, `title` | Yes |
| `priority` | Yes, mapped to `data` keys (below) |
| `image` | Yes, as `data.image` |
| `data` | Yes: the `mobile_app` block, any key |
| `click_action`, `tag`, `car_ui` | Yes, mapped to `data` keys (below) |
| `actions` | Yes, with [responses](#actions-and-responses) |

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

## Click action, tag, car UI and actions

These typed fields are mapped to the companion app's keys; the `mobile_app`
block of `data` is merged over them, so it can override them:

| Field | Sent as |
| --- | --- |
| `click_action` | `clickAction` (Android) and `url` (iOS) |
| `actions` | `actions`, with `id` as `action` and `label` as `title` |
| `tag` | `tag` |
| `car_ui` | `car_ui: true` (nothing when off) |

The iOS `url` key is from the companion app documentation and has not been
checked on a device.

## Actions and responses

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
| `tag` | The notification's `tag`, none if it had no tag or has left [history](../history.md) |
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
[history](../history.md) and shown under Recent. If the notification has
already left history the event is still fired. Actions with a `uri` open it
and send no response. Responses to notifications that Com System did not
send are ignored. Automations that listen to `mobile_app_notification_action`
directly see the encoded ID, so use `com_system_action`, which has the
original one.

In the [testing tool](../ui.md#test), enter the actions in the `data` field
like any other receiver content; the form has no action editor of its own.

## Which person a device belongs to

A device is linked to at most one person, found each time it is needed so
later changes to people are picked up:

1. The person linked to the Home Assistant user the app is registered with.
2. Otherwise, the person whose device trackers include the app's device
   tracker.
3. Otherwise, no person.

The person cannot be chosen: there is no people option for a mobile app
receiver. To change it, link the person to the right Home Assistant user or
device tracker.

## Personal or shared

Each mobile app receiver has a **Device use** select entity (a
configuration entity) on its device, with two options:

- **Personal**: the device is reached when its person is targeted.
- **Shared** (for example a wall tablet): the device has no person, so it is
  never reached by a person target. It is still reached by area or by naming
  it.

A new receiver starts as personal when a person is linked and as shared
when not. The choice is kept across restarts. Change it on the
device page (under Configuration) or with the `select.select_option`
action:

```yaml
action: select.select_option
target:
  entity_id: select.pixel_device_use
data:
  option: shared
```
