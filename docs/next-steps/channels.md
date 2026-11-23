# Channels

A channel is a named set of default notification content. Select it in the
`channel` field of [notify.com_system](../services.md) and the channel's
defaults fill anything the call leaves out. Channels are useful beyond the
mobile app: they are a way to reuse a set of options.

## Defaults

A channel can default `title`, `priority`, `image`, `click_action`,
`actions`, `tag`, `car_ui` and `data`. Whatever a
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

Channels are written with three actions, and the **Channels** page of the
Com System panel is a front end for them: its forms are Home Assistant's own
action forms, built from the actions' descriptions. Channels are stored with
the hub, so they do not appear as separate entries in Devices & services,
and no configuration or options dialog edits them. Each has a
`notification_channel` entity whose state is its name and whose attributes
are its defaults.

- `com_system.create_channel`: creates a channel. Fields: `name`, and any of
  `title`, `priority`, `image`, `click_action`, `actions`, `tag`, `car_ui`
  and `data`. Names are unique, ignoring case.
- `com_system.update_channel`: renames a channel and **replaces** its
  defaults, so any that are not given are cleared. Fields: `channel` (the
  entity), an optional `name`, and any of the defaults.
- `com_system.delete_channel`: deletes a channel. Field: `channel` (the
  entity).

`create_channel` and `update_channel` return the channel (`channel_id`,
`name`, `entity_id`, `defaults`) when a response is requested. `image` is
an http(s) URL, a `/local/` path, a `media-source://` ID, or an image or
camera entity ID. `data` is keyed by receiver type.

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
On the Channels page, **Edit** opens the update form filled with the
channel's current values.
