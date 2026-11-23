# Receiver person

A receiver's person decides when it is reached by a **people** target:
**Everyone** reaches every receiver that has a person, and **Individuals**
reaches the receivers of the people you pick. A receiver with no person is
never reached by a people target, but can still be reached by area or by
name. See [targets](../targets.md).

How the person is set depends on the receiver type.

## Mobile app

The person is found automatically, each time it is needed, so changes to
people are picked up:

1. The person linked to the Home Assistant user the app is registered with.
2. Otherwise, the person whose device trackers include the app's device
   tracker.
3. Otherwise, no person.

It cannot be chosen on the receiver. To change it, link the person to the
right Home Assistant user or device tracker.

### Personal or shared

Each mobile app receiver has a **Device use** select entity (a
configuration entity) on its device:

- **Personal**: the device is reached when its person is targeted.
- **Shared** (for example a wall tablet): the device has no person, so it is
  never reached by a person target. It is still reached by area or by naming
  it.

A new receiver starts as personal when a person is linked and as shared when
not. The choice is kept across restarts. Change it on the device page (under
Configuration) or with the `select.select_option` action:

```yaml
action: select.select_option
target:
  entity_id: select.pixel_device_use
data:
  option: shared
```

## Other receivers

Where a receiver cannot work out its person, set it by hand: choose
**Configure** on the receiver (from its device page or Devices & services)
and pick the person. Leave it empty if the receiver is not tied to anyone.

| Receiver | Person |
| --- | --- |
| [Pushover](../receivers/pushover.md) | Set by hand (at most one) |
| [Alexa Media Player](../receivers/alexa-media-player.md) | Set by hand; most Echoes are shared, so reach them by area |
| [Custom](../receivers/custom.md) | Set by hand |
| [Persistent notification](../receivers/persistent-notification.md) | None; cannot be set |
| [webOS TV](../receivers/webostv.md) | None; cannot be set |

The same form has the receiver's
[notification conditions](../conditions.md), which every receiver type
offers.
