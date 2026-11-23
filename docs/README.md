# Com System documentation

Documentation for the Com System integration. It is written alongside the
code and describes the integration as built. The development environment is
described in the [repository README](../README.md#development).

## Getting started

[Getting started](getting-started.md) is a single page guide from
installation to your first notification.

## Next steps

- [Dashboard](next-steps/dashboard.md): the sidebar panel, the history of
  notifications sent, and the websocket commands behind them.
- [Receiver person](next-steps/person.md): how a receiver's person is found
  or set.
- [Receiver areas](next-steps/areas.md): how a receiver's area is
  determined and changed.
- [Channels](next-steps/channels.md): named defaults for notifications, and
  Android notification channels.

## Receivers

[Receivers](receivers/README.md) explains the receiver concept, automatic
detection and receiver entities. Each type has a page covering its
integration, features, notification parameters and other details:

- [Mobile app](receivers/mobile-app.md)
- [Alexa Media Player](receivers/alexa-media-player.md)
- [Pushover](receivers/pushover.md)
- [webOS TV](receivers/webostv.md)
- [Persistent notification](receivers/persistent-notification.md)
- [Custom receivers](receivers/custom.md): scripts as receivers

## Reference

- [The notify.com_system action](services.md): sending a notification, its
  fields, delivery and the per-receiver response.
- [Targets](targets.md): how people, areas and receivers decide where a
  notification goes.
- [Content](content.md): priority, images, per-type `data`, capabilities
  and dropped content.
- [Notification conditions](conditions.md): rules that skip a receiver
  for a notification, and the variables they can use.
- [Commands](commands.md): actions that control receivers, such as
  clearing a notification.
- [Triggers](triggers.md): starting automations from notification actions.
