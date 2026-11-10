# Receivers

A receiver is a configured endpoint that Com System can deliver a
notification to. Com System has one hub config entry and one config entry
per receiver.

## Receiver types

Every receiver has a type that defines how it is discovered, which content
it supports and how a notification is delivered to it. Types are defined in
code, so new types can be added without changing the receiver model.

## Automatic detection

The hub finds the devices and integrations that can receive notifications
and offers each as a discovery on **Settings > Devices & services**. You
decide for each one:

- **Add** creates the receiver. New receivers start enabled.
- **Ignore** stops that device ever being offered again. To offer it again,
  delete the ignored entry from the integration's **Ignored** list.

Detection runs whenever the hub loads (so after every restart), a few
seconds after the device registry changes, and once an hour. Each source
device is offered once, however often detection runs. These types are
detected:

| Type | One receiver for each |
| --- | --- |
| Mobile app | registered mobile app device |
| Alexa Media Player | Echo device (only if the integration is installed) |
| Persistent notification | Home Assistant (a single receiver) |
| Pushover | Pushover config entry |
| webOS TV | webOS TV config entry |
| Music Assistant | Music Assistant player |

Detection offers receivers. Sending is added as each type is built. So far
[Persistent notification](persistent-notification.md) and
[mobile app](mobile-app.md) receivers send.

### Deleting, disabling and removed devices

- A receiver you **delete** is offered again at the next detection, unless
  you ignored it. To stop a receiver being used without deleting it, turn
  off its enabled switch rather than disabling its config entry, which
  removes its entities.
- If the device or integration a receiver came from is **removed**, the
  receiver is kept, with its settings, and shown as unavailable. If the
  device returns, the receiver is reloaded at the next detection and works
  again. Remove stale receivers yourself.

## Custom receivers

A custom receiver is a script that takes a `notification` object; see
[custom receivers](custom.md).

## People and areas

Choose **Configure** on a receiver to set the people it relates to (not
offered for receiver types that cannot relate to a person, such as
Persistent notification). Com
System uses this to find the receivers for a person. Leave it empty if the
receiver is not tied to anyone.

A receiver's area is not set here. It is the area of the receiver's device
in Home Assistant (or of its entity, if that has its own area). To change
it, change the area of the device.

## Receiver entities

Each receiver has a device with two entities. Mobile app receivers have a
third, [Device use](mobile-app.md#personal-or-shared).

- **Enabled** (`switch`): on means the receiver is enabled, off means it
  is disabled. New receivers are enabled, and the state is kept across
  restarts. Use the normal switch controls and the `switch.turn_on`,
  `switch.turn_off` and `switch.toggle` actions, for example in an
  automation that turns a receiver off at night and on in the morning.
- **Receiver** (`notification_receiver`): read-only. Its state is the time
  of the last notification attempt, or `unknown` before the first. Its
  `event_type` attribute is the result (`delivered`, `failed` or
  `skipped`). Further attributes hold the last notification (`title`,
  `message`, `priority`, `image`, `data`), any `warnings`, and the
  receiver's `receiver_type`, `people` and `areas` (the device's area). It has
  no actions. To react to a notification, use a state trigger on this entity.

The receiver entity stays `unknown` until the receiver is notified.

## The receiver registry

Com System keeps a registry of all receivers, built from the receiver
config entries. It is available as soon as Home Assistant has set up the
integration, so receivers work in any load order and without the hub. If a
receiver's type is no longer available, the receiver is kept so it is not
lost.
