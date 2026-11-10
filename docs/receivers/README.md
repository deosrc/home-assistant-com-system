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

Detection only offers receivers. Sending notifications to each type is
added as that type is built.

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

A custom receiver is added manually: with the hub in place, choose **Add
integration** and **Com System**, then give the receiver a name. Mapping a
receiver to Home Assistant actions is not implemented yet.

## People and areas

Choose **Configure** on a receiver to set the people and areas it relates
to. Com System uses these to find the receivers for a person or an area.
Leave both empty if the receiver is not tied to either.

## The receiver registry

Com System keeps a registry of all receivers, built from the receiver
config entries. It is available as soon as Home Assistant has set up the
integration, so receivers work in any load order and without the hub. If a
receiver's type is no longer available, the receiver is kept so it is not
lost.
