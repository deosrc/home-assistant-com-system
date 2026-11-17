# Commands

Commands control receivers instead of notifying them. Each is a Com System
action, `com_system.<command>`, that takes the same `people` and `receivers`
[targets](targets.md) as `notify.com_system`. They wrap the awkward
"notification commands" of the Home Assistant companion app, so you do not
have to send a notification with a special `message` to a device's
`notify.mobile_app_*` action.

A receiver whose type does not support the command (or whose device OS does
not) is skipped with a reason; it is not an error. A command raises an error
only when nothing could be attempted: no targets, no receiver matched, or
every match is disabled. Commands are not kept in the [history](history.md)
and do not update the receiver entity.

Like `notify.com_system`, a command returns a response (when requested) with
`results` for each receiver (`entry_id`, `name`, `type`, `result`, `reason`,
`warnings`) and `counts`. Results are `delivered`, `failed` or `skipped`.
`delivered` means the device's notify action was called; the app gives no
confirmation.

## Available commands

| Command | Fields | Receiver types |
| --- | --- | --- |
| `com_system.clear_notification` | `tag` (required) | Mobile app, persistent |

### Clear a notification

Removes the notification with the given `tag` from the targeted devices. Send
the notification with a `tag` first (see [content](content.md)); this is the
same tag.

```yaml
action: com_system.clear_notification
data:
  tag: front-door
  people:
    active_choice: Everyone
    Everyone: true
```

On mobile apps it sends the app's `clear_notification` command with
`data.tag`. For persistent notifications it dismisses the notification Com
System made for that tag, so only notifications sent with a tag can be
cleared there.

## Adding a command

Commands are written to be easy to add:

1. Add a `Command` to `COMMANDS` in `commands.py`, with its parameters as a
   voluptuous schema. The targets are added for you. Describe it in
   `services.yaml`, `strings.json` (and its copy in `translations/en.json`)
   and `icons.json`; a test checks all four agree.
2. Implement it for each receiver type that supports it: list it in the
   type's `commands` and handle it in `async_command` (override
   `supports_command` when support depends on the receiver). For the mobile
   app add a `MobileAppCommand` to `MOBILE_APP_COMMANDS` in `mobile_app.py`:
   the app's message, how to build its `data` from the parameters and,
   for an OS-specific command, `os_names` (such as `frozenset({"android"})`).
3. Document it here.
