# Alexa Media Player receivers

An Alexa Media Player receiver announces notifications on one Echo device.
It needs the custom [Alexa Media Player](https://github.com/alandtse/alexa_media_player)
integration (domain `alexa_media`). Com System offers one receiver for each
Echo device the integration has registered (see
[automatic detection](README.md#automatic-detection)); nothing is offered if
the integration is not installed.

## Delivery

A notification is delivered by calling the integration's `notify.alexa_media`
action with `type: announce`, the Echo's serial number as the target, the
message and, when given, the title. The Echo speaks the message and devices
with a screen also show the title. Priority, images and `data` are not
supported.

If the action does not exist (the integration is not installed or not yet
loaded) the delivery fails for that receiver only, with the reason in the
result. If the Echo's device is removed, the receiver is shown as unavailable
and returns when the device does (see
[removed devices](README.md#deleting-disabling-and-removed-devices)).

Announcements are not sent to a device the integration reports as offline;
the integration skips it without an error, so Com System reports delivered.
Announcements are also silently skipped on a second Amazon account's
devices, whose target id is not the serial number.

## People and areas

- **Area:** the receiver's entities sit on the Echo's own device, so its area
  is the area of that device. Set it on the device page; Com System
  does not set it.
- **Person:** an Echo has no link to a person, so none is found. Choose
  **Configure** on the receiver to set one manually. Most Echoes are shared,
  so reaching them by area is usual.
