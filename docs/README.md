# Com System documentation

Com System is a notification distribution system for Home Assistant focusing
on a publish-subscribe approach. Put simply, a notification is sent which
usually targets an area and/or person, and registered receivers for those
areas or people process it.

Main Features:

- A UI for each monitoring and management. No YAML.
- Notification receivers for areas, people, or standalone
- Rich send notification action making composing complex notification easier
- Receiver conditions based on Home Assistant conditions or notification content
- A trigger for press notification actions (Home Assistant mobile app only)
- Channels to configure defaults across notification types, and Android
  notification channels

Supported Receivers (at the time of writing):

- Persistent Notification (Home Assistant Notifications Panel)
- Home Assistant Mobile App
- Pushover
- WebOS TVs
- Alexa Media Player

## Getting started

See [Getting started](getting-started.md) for a walkthrough from zero to your
first notification.

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

See [Receivers](receivers/README.md) explains the receiver concept, automatic
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
