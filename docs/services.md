# The notify.com_system action

Com System adds one action, `notify.com_system`, to Home Assistant's
`notify` domain. Call it from an automation, script or Developer tools to
send a notification to the receivers that match its [targets](targets.md).

## Fields

| Field | Required | Description |
| --- | --- | --- |
| `title` | no | A title; folded into the message where there is none. |
| `message` | yes | The message to send. |
| `priority` | no | `low`, `normal` (default), `high` or `critical`. |
| `image` | no | An http(s) URL, `/local/` path or media source ID. |
| `data` | no | Receiver-specific content, keyed by receiver type. |
| `people` | no | Individual people, or everyone (see below). |
| `receivers` | no | Selected receivers, or all areas (see below). |

`people` and `receivers` are the targets. They are combined as a union;
see [targets](targets.md). A field that is not given is not targeted, so
with only `receivers` no person is targeted, and the other way round. Give
at least one. In the form, untick a field to leave it out. The form starts with
**Everyone** and **All Areas**, as the Test page does.

### People

`people` is a choice between **Individuals** and **Everyone**. Individuals
reaches the receivers of the `person.*` entities you pick, and picking none
adds no people (use this to target only receivers). Everyone reaches every
receiver that is associated with any person. In YAML:

```yaml
people:
  active_choice: Individuals
  Individuals:
    - person.alice
```

```yaml
people:
  active_choice: Everyone
  Everyone: true
```

A plain `person.*` entity or list of them is also accepted and means
individuals.

### Receivers

`receivers` is a choice between **Select** and **All Areas**. All Areas
reaches every receiver that has an area. Select shows a target selector
limited to receivers (the `notification_receiver` entities), where you can
also pick areas, and devices, floors and labels, which reach the receivers
they contain. In YAML:

```yaml
receivers:
  active_choice: Select
  Select:
    entity_id:
      - notification_receiver.alice_s_phone
    area_id: kitchen
```

```yaml
receivers:
  active_choice: All Areas
  All Areas: true
```

A plain target (`entity_id`, `area_id` and so on, without `active_choice`)
is also accepted and means Select. An `entity_id` that is not a Com System
receiver matches nothing. See [targets](targets.md) for which receivers
people and areas reach.

Priority, image and `data` are described in [content](content.md); a
receiver that does not support some of it drops it and reports a warning.
Input that does not fit the fields is rejected before anything is sent.

```yaml
action: notify.com_system
data:
  title: Laundry
  message: The washing has finished
  people:
    active_choice: Individuals
    Individuals:
      - person.alice
  receivers:
    active_choice: Select
    Select:
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
    reasons: # why it was included: its area or person, or it was named
      - kind: person # everyone, all_areas, person, area or receiver
        id: person.alice # not set for everyone and all_areas
counts:
  delivered: 1
  failed: 0
  skipped: 0
```

Ignoring the response is fine: the action works without
`response_variable`.

## Errors

The action raises an error only when nothing could be attempted:

- the input is invalid (for example `message` is missing),
- neither `people` nor `receivers` is given, or
- no receiver matches the targets, or every receiver that matches is
  disabled.

A receiver failing is not an error; check `results` or `counts.failed`. In
an automation, an error stops the run unless the step has
`continue_on_error: true`.

## Testing

The **Test** page of the [panel](ui.md#test) sends through this same action
and shows which receivers a notification would reach before it is sent.
