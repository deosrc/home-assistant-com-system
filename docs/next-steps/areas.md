# Receiver areas

A receiver's area decides when it is reached by an **area** target, and by
**All Areas**. See [targets](../targets.md).

## How the area is determined

A receiver's area is not stored by Com System. It is the area of the
notification receiver entity, or the device that entity is assigned to.

For example, a notification receiver with no area, created for a WebOS TV
which is assigned to the Living Room area, will be notified for anything
targeting the Living Room (or all areas).

The [Receivers page](dashboard.md#receivers) shows the area for each
notification receiver.

A receiver with no area is never reached by an area, floor or **All Areas**
target. It can still be reached by person, or named. The persistent
notification receiver starts with no area.

## Setting the area

The recommended way to set the area of a notification receiver is to set the
area for the device. This should take effect immediately.
