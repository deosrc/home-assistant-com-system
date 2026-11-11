# Mobile app receivers

A mobile app receiver sends notifications to one device that runs the Home
Assistant companion app. Com System offers one receiver for each registered
device (see [automatic detection](README.md#automatic-detection)).

## Delivery

A notification is delivered by calling the device's own
`notify.mobile_app_<device name>` action with the message and, when given,
the title. If that action does not exist (for example the device has no push
support or was removed) the delivery fails for that receiver only, with the
reason in the result. Priority, images and `data` are not supported yet.

## Which person a device belongs to

A device is linked to at most one person, found each time it is needed so
later changes to people are picked up:

1. The person linked to the Home Assistant user the app is registered with.
2. Otherwise, the person whose device trackers include the app's device
   tracker.
3. Otherwise, no person.

A person set on the receiver with **Configure** overrides this link.

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
