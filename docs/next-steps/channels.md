# Channels

A channel is a named set of default notification content, or for Android
Notification Channels.

Select it in the `channel` field of [notify.com_system](../services.md) and
the channel's defaults fill anything the call leaves out. Channels are useful
beyond the mobile app: they are a way to reuse a set of options.

## Defaults

A channel can default most properties used when sending notifications.
Whatever a notification sets itself wins so individual channel properties
can be overridden.

```yaml
action: notify.com_system
data:
  message: Someone is at the door
  channel: Doors
  title: Front Door   # beats the channel's title
```

In the example above, the "Doors" channel is used. If "Doors" is set as the
title, the title used will still be "Front Door" as it takes priority. 

`data` if provided is merged key by key in the same manner

## Mobile apps

The channel name is also sent as the Android notification channel
(`data.channel`), so you do not need to remember it in each call. The
`mobile_app` block of `data` is merged last and can override it.

When a channel is removed, or renamed, Com System automatically sends the
`remove_channel` notification to every Android mobile app receiver, so the
channel disappears from the device. iOS devices are not sent it. A device
that cannot be reached is logged and skipped. The channel will still be
removed from Com System regardless.

## Managing channels

The recommended way to manage channels is via the Com System UI, however,
they can also be managed via Home Assistant Actions.

As with other parts of Com System, notification channels are created as
entities in the `notification_channel` domain so that they can be used in
selectors. They are assigned to the Com System hub device. The attributes
contain the notification channel defaults.

### Actions

- `com_system.create_channel`: creates a channel. Names are unique, ignoring
  case.
- `com_system.update_channel`: renames a channel and **replaces** its
  defaults, so any that are not given are cleared.
- `com_system.delete_channel`: deletes a channel.

```yaml
action: com_system.create_channel
data:
  name: Doors
  priority: high
  data:
    mobile_app:
      tag: door
```

Renaming or deleting a channel removes the old name from Android devices.
