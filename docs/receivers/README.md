# Receivers

A receiver is a configured endpoint that Com System can deliver a
notification to. Com System has one hub config entry and one config entry
per receiver.

## Receiver types

Every receiver has a type that defines how it is discovered, which content
it supports and how a notification is delivered to it. Types are defined in
code, so new types can be added without changing the receiver model.

## Custom receivers

A custom receiver is added manually: with the hub in place, choose **Add
integration** and **Com System**, then give the receiver a name. Mapping a
receiver to Home Assistant actions is not implemented yet.

## People and areas

Choose **Configure** on a receiver to set the people and areas it relates
to. Com System uses these to find the receivers for a person or an area.
Leave both empty if the receiver is not tied to either.

## Receiver entities

Each receiver has a device with two entities.

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
  receiver's `receiver_type`, `people` and `areas`. It has no actions. To
  react to a notification, use a state trigger on this entity.

Sending notifications is not implemented yet, so the receiver entity stays
`unknown` for now.

## The receiver registry

Com System keeps a registry of all receivers, built from the receiver
config entries. It is available as soon as Home Assistant has set up the
integration, so receivers work in any load order and without the hub. If a
receiver's type is no longer available, the receiver is kept so it is not
lost.
