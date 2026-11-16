# Channels

A channel is a named set of default notification content. Name it in the
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

A call that names a channel that does not exist fails and sends nothing.

## Mobile apps

The channel name is also sent as the Android notification channel
(`data.channel`), so you do not need to remember it in each call. The
`mobile_app` block of `data` is merged last and can override it.

When a channel is removed, or renamed, Com System sends the
`remove_channel` notification to every Android mobile app receiver, so the
channel disappears from the device. iOS devices are not sent it. A device
that cannot be reached is logged and skipped; the channel is removed anyway.

## Managing channels

Channels are managed with the `com_system/channels/*`
[websocket commands](ui.md#websocket-commands). The panel does not have a
channels page yet.
