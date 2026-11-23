# Triggers

## Com System notification action received

`com_system.action_received` starts an automation when someone responds to a
notification action, such as a button on a [mobile app
notification](receivers/mobile-app.md#actions-and-responses). It is
available in the automation editor as **Com System notification action
received**.

| Option | Required | Description |
| --- | --- | --- |
| `action` | yes | The `id` of the action that was pressed. |
| `notification_id` | see below | The `id` that `notify.com_system` returned. |
| `tag` | see below | The notification's `tag`. |

The action is always required, with the notification ID or the tag, or both.
When both are given, both must match. A trigger with only an action is
rejected, so an action ID shared by several notifications cannot start
automations by accident.

```yaml
triggers:
  - trigger: com_system.action_received
    options:
      action: OPEN
      tag: front-door
actions:
  - action: cover.open_cover
    target:
      entity_id: cover.gate
```

The trigger variables are the keys of the
[`com_system_action` event](receivers/mobile-app.md#actions-and-responses):
`trigger.action`, `trigger.notification_id`, `trigger.tag`,
`trigger.receiver_id`, `trigger.receiver`, `trigger.person` and
`trigger.reply_text`.

The tag is carried in the action ID the app is sent, so it is known even when
the notification has since been removed from
[history](next-steps/dashboard.md#history).

The trigger fires from the `com_system_action` event, so you can also use an
`event` trigger on it. This trigger adds the form in the editor and the
required options.
