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

`priority` is mapped to the companion app's keys; each platform ignores the
other's:

- `low`: Android `importance: low`; iOS `passive`.
- `normal`: nothing.
- `high`: Android `importance: high`, `ttl: 0`, `priority: high`; iOS
  `time-sensitive`.
- `critical`: Android `importance: max`, `ttl: 0`, `priority: high`; iOS
  `critical` with a critical sound at full volume.

`image` is passed as `data.image`; a media source ID is resolved to a URL
first (if it cannot be, the image is dropped with a warning). The
`mobile_app` block of `data` is merged over these, so it can override them
and add keys such as `actions`, `tag` or `channel`:

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

Responses to notification actions are not supported yet.

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
