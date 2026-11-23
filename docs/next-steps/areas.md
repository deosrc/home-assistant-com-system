# Receiver areas

A receiver's area decides when it is reached by an **area** target, and by
**All Areas**. See [targets](../targets.md).

## How the area is determined

A receiver's area is not stored by Com System. It is the area of the
receiver's device in Home Assistant, or of its entity if that has its own
area. The receiver's `notification_receiver` entity lists it in its `areas`
attribute, and the [Receivers page](dashboard.md#receivers) shows it as a
badge.

Where the device comes from depends on the type:

| Receiver | Device the area comes from |
| --- | --- |
| [Mobile app](../receivers/mobile-app.md) | The phone or tablet's own device |
| [Alexa Media Player](../receivers/alexa-media-player.md) | The Echo's own device |
| [webOS TV](../receivers/webostv.md) | The TV's own device |
| [Pushover](../receivers/pushover.md) | A new device made for the receiver |
| [Persistent notification](../receivers/persistent-notification.md) | A new device made for the receiver |
| [Custom](../receivers/custom.md) | A new device made for the receiver |

## Setting the area

Change the area where it comes from, in Home Assistant: open the receiver's
device page (click the receiver in the panel) and set its **Area**. For a
device that belongs to another integration, such as an Echo, this also
changes the area of that integration's device.

A receiver with no area is never reached by an area, floor or **All Areas**
target. It can still be reached by person, or named. The persistent
notification receiver starts with no area.
