# Channels

A channel is a named set of default notification content. Select it in the
`channel` field of [notify.com_system](services.md) and the channel's
defaults fill anything the call leaves out. Channels are useful beyond the
mobile app: they are a way to reuse a set of options.

## Defaults

A channel can default `title`, `priority`, `image` and `data`. Whatever a
call sets itself wins. `data` is merged key by key, with the call's keys
winning:

```yaml
action: notify.com_system
data:
  message: Someone is at the door
  channel: Doors
  priority: low   # beats the channel's priority
```

The field takes a `notification_channel` entity (`channel:
notification_channel.doors`); the form's picker lists only channels. Any
other entity fails the call and sends nothing.

## Mobile apps

The channel name is also sent as the Android notification channel
(`data.channel`), so you do not need to remember it in each call. The
`mobile_app` block of `data` is merged last and can override it.

When a channel is removed, or renamed, Com System sends the
`remove_channel` notification to every Android mobile app receiver, so the
channel disappears from the device. iOS devices are not sent it. A device
that cannot be reached is logged and skipped; the channel is removed anyway.

## Managing channels

Use the **Channels** page of the Com System panel. Channels are stored with
the hub, so they do not appear as separate entries in Devices & services,
and no configuration or options dialog edits them. Each has a
`notification_channel` entity whose state is its name and whose attributes
are its defaults.

- **Add**: **Add channel**, then a name and any defaults. Names are unique,
  ignoring case. `data` is JSON keyed by receiver type.
- **Edit or rename**: **Edit**. A rename removes the old name from Android
  devices.
- **Delete**: **Delete**.
