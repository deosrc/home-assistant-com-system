# Alexa Media Player receiver

## Integration

Announces notifications on an Echo device, using the custom
[Alexa Media Player](https://github.com/alandtse/alexa_media_player)
integration (domain `alexa_media`). One receiver is offered for each Echo
device the integration has registered; nothing is offered if the integration
is not installed.

## Features

- The Echo speaks the message, and devices with a screen also show the
  title.
- The receiver's area is the area of the Echo's own device (see
  [areas](../next-steps/areas.md)).
- An Echo has no link to a person, so none is found. Most Echoes are shared,
  so reaching them by area is usual; set a person by hand if needed (see
  [person](../next-steps/person.md)).

## Notification parameters

| Parameter | Supported | Mapping |
| --- | --- | --- |
| `message` | Yes | `tts` [message type](../content.md#message-types), else `text` |
| `title` | Yes | `title` |
| `priority`, `image`, others | No | Dropped, with a warning |
| `data` | No | Dropped, with a warning |

There are no receiver-specific `data` options.

## Other information

A notification is delivered by calling the integration's `notify.alexa_media`
action with `type: announce` and the Echo's serial number as the target. If
the action does not exist (the integration is not installed or not yet
loaded) the delivery fails for that receiver only, with the reason in the
result. If the Echo's device is removed, the receiver is shown as
unavailable and returns when the device does (see
[removed devices](README.md#deleting-disabling-and-removed-devices)).

Announcements are not sent to a device the integration reports as offline;
the integration skips it without an error, so Com System reports delivered.
They are also silently skipped on a second Amazon account's devices, whose
target id is not the serial number.
