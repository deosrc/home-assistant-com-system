# Notification conditions

A receiver can have **conditions** that decide, notification by
notification, whether it is used. They are separate from the receiver's
[enabled](receivers/README.md) switch, which blocks every notification.

## Setting conditions

Choose **Configure** on a receiver (its device page, or **Settings >
Devices & services > Com System**) and use **Conditions**. It is Home
Assistant's own condition editor, the one automations use, so template,
state, numeric state, time, and `and`/`or`/`not` conditions all work.
Conditions belong to one receiver; there are no shared sets. They are
stored in the receiver's options.

All conditions must pass. A receiver with none always passes.

## When they are evaluated

1. [Targets](targets.md) are resolved to receivers.
2. Disabled receivers are skipped.
3. Each remaining receiver's conditions are evaluated.
4. Receivers that pass are delivered to.

A receiver whose conditions do not pass is skipped for that notification
only. The result is `skipped` with the reason `Conditions did not pass`,
in the [action response](services.md), the receiver entity's last result,
[history](history.md) and the [Test page](ui.md#test).

## Variables

Templates can use three variables.

- `notification`: `id`, `title`, `message`, `priority` and `image` (`none`
  when not given), `data` (an object, empty when not given), `targets` (the
  `people` and `receivers` the call asked for) and any other content field
  that was given (`click_action`, `actions`, `tag`, `car_ui`, `channel`).
- `receiver`: `name`, `type` (the type's name), `type_id`, `entry_id`,
  `entity_id` (its `notification_receiver` entity), and `people` and
  `areas` (lists).
- `resolved_targets`: why the receiver matched, a list of `kind`
  (`everyone`, `all_areas`, `person`, `area` or `receiver`) and `id` (absent
  for `everyone` and `all_areas`).

The `notification` is the content before any receiver type drops
unsupported fields. Use `notification.get('key')` or `| default` for the
content fields that are only present when given.

The `state` condition's `state` is not a template and cannot use these
variables.

## Errors

A condition that errors (a template that fails to render, a state
condition on a missing entity) counts as not passed. The receiver is
skipped with the reason `Condition error: ...`, the error is logged, and
it is recorded like any other skip. This fails safe for rules such as
do-not-disturb. Conditions that no longer validate are an error too. An
`or` ignores an erroring branch if another branch is true.

## Examples

Skip a receiver when the message contains some text:

```yaml
- condition: template
  value_template: "{{ 'secret' not in notification.message }}"
```

Only deliver at night to a receiver:

```yaml
- condition: time
  after: "22:00:00"
  before: "07:00:00"
```

Only deliver low priority notifications when someone is home:

```yaml
- condition: or
  conditions:
    - condition: template
      value_template: "{{ notification.priority != 'low' }}"
    - condition: state
      entity_id: zone.home
      state: "1"
```

Only deliver when the receiver was reached through its person, using
`resolved_targets`:

```yaml
- "{{ resolved_targets | selectattr('kind', 'eq', 'person') | list | length > 0 }}"
```

The **Test** page evaluates the conditions with the message, title and
other content in its form, so you can try them before sending.
