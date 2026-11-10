# The notify.com_system action

Com System adds one action, `notify.com_system`, to Home Assistant's
`notify` domain. Call it from an automation, script or Developer tools to
send a notification to the receivers that match its [targets](targets.md).

## Fields

| Field | Required | Description |
| --- | --- | --- |
| `message` | yes | The message to send. |
| `title` | no | A title; folded into the message where there is none. |
| `person` | no | One or more `person.*` entities. |
| `area_id` | no | One or more areas. |
| `entity_id` | no | One or more `notification_receiver` entities. |

`person`, `area_id` and `entity_id` are the targets. They are combined as a
union, and with none of them the notification goes to all people and all
areas; see [targets](targets.md). An `entity_id` that is not a Com System
receiver matches nothing, but still counts as a target, so it never falls
back to the default.

Priority, images and receiver-specific `data` are not supported yet. Input
that does not fit the fields is rejected before anything is sent.

```yaml
action: notify.com_system
data:
  title: Laundry
  message: The washing has finished
  person:
    - person.alice
  area_id: kitchen
```

## Delivery

Each receiver is delivered to independently and at the same time. One
receiver failing, or raising an error, never stops the others. Receivers
that matched but are disabled are skipped.

Every outcome is recorded on the receiver's `notification_receiver` entity
(see [receivers](receivers/README.md)), including failed and skipped
attempts, together with the notification's content and any warnings.
Failures are also logged.

A receiver type whose delivery is not built yet reports `failed` with the
reason "Delivery is not implemented for this receiver type".

## Response

The action supports a response (`response_variable` in an automation). It
lists the outcome for each receiver, ordered by name, and a count of each
outcome:

```yaml
results:
  - entry_id: 01J...
    name: Alice's phone
    type: Mobile app
    result: delivered # delivered, failed or skipped
    reason: null # why it failed or was skipped
    warnings: [] # content the receiver dropped
counts:
  delivered: 1
  failed: 0
  skipped: 0
```

Ignoring the response is fine: the action works without
`response_variable`.

## Errors

The action raises an error only when nothing could be attempted:

- the input is invalid (for example `message` is missing), or
- no receiver matches the targets, or every receiver that matches is
  disabled.

A receiver failing is not an error; check `results` or `counts.failed`. In
an automation, an error stops the run unless the step has
`continue_on_error: true`.

## Testing

The **Test** page of the [panel](ui.md#test) sends through this same action
and shows which receivers a notification would reach before it is sent.
