# Receivers

A receiver is a configured endpoint that Com System can deliver a
notification to. Com System has one hub config entry and one config entry
per receiver.

## Receiver types

Every receiver has a type that defines how it is discovered, which content
it supports and how a notification is delivered to it.

- [Alexa Media Player](alexa-media-player.md): Echo announcements.
- [Mobile app](mobile-app.md): Home Assistant companion app devices.
- [Persistent notification](persistent-notification.md): the Home Assistant
  notification area.
- [Pushover](pushover.md): Pushover devices.
- [webOS TV](webostv.md): toasts on LG TVs.

[Custom receivers](custom.md) can also be created if your receiver type isn't
supported, or if you require more advanced functionality.

## Automatic detection

The hub finds the devices and integrations that can receive notifications
and offers each as a discovery on **Settings > Devices & services**.

- **Add** creates the receiver. New receivers start enabled.
- **Ignore** stops that device ever being offered again. To offer it again,
  delete the ignored entry from the integration's **Ignored** list.

Detection runs whenever the hub loads (so after every restart), a few
seconds after the device registry changes, and once an hour.

### Deleting, disabling and removed devices

- A receiver you **delete** is offered again at the next detection, unless
  you ignored it. To stop a receiver being used without deleting it, turn
  off its switch rather than disabling its config entry.
- If the device or integration a receiver came from is **removed**, the
  receiver is kept, with its settings, and shown as unavailable. If the
  device returns, the receiver is reloaded at the next detection and works
  again. Stale receivers must be removed manually.

## People and areas

A receiver's person and area decide which targets reach it. See
[receiver person](../next-steps/person.md) and
[receiver areas](../next-steps/areas.md). The **Configure** form also has
the receiver's [notification conditions](../conditions.md), which every
receiver type offers.

## Receiver entities

Each receiver has a device with at least two entities, or adds the entities
to the device it is based on.

- **Receiver** (`notification_receiver`): read-only. Its state is the time
  of the last notification attempt, or `unknown` before the first. Its
  `event_type` attribute is the result (`delivered`, `failed` or
  `skipped`). Further attributes hold the last notification (`title`,
  `message`, `priority`, `image`, `data`), any `warnings`, and the
  receiver's `receiver_type`, `people` and `areas` (the device's area).
- **Notifications Enabled** (`switch`, a configuration entity): on means
  the receiver is enabled, off means it is disabled. New receivers are
  enabled, and the state is kept across restarts. Use the normal switch
  controls and the `switch.turn_on`, `switch.turn_off` and `switch.toggle`
  actions, for example in an automation that turns a receiver off at night
  and on in the morning.
