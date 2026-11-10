# Custom receivers

A custom receiver is a Home Assistant script. Com System detects suitable
scripts and offers each one as a receiver, like any other
[detected receiver](README.md#automatic-detection). You write the script, so
it can do anything Home Assistant can.

## Which scripts are detected

A script is offered only when it has exactly one field, named
`notification`, with the **object** selector. Scripts with no fields,
other fields, or another selector are ignored.

```yaml
script:
  living_room_speaker:
    alias: Living room speaker
    fields:
      notification:
        selector:
          object:
    sequence:
      - action: notify.living_room_speaker
        data:
          message: "{{ notification.title }}: {{ notification.message }}"
```

Detection runs when the hub loads, after scripts are reloaded or added, and
once an hour. Choose **Add** on the discovery to create the receiver, or
**Ignore** to never be offered that script again.

## What the script receives

The whole notification is passed in the `notification` field, as a mapping:
`message` and, when given, `title`. Fields added to the action later are
passed the same way, so a script should read what it needs and ignore the
rest. Custom receivers declare no capabilities, so no unsupported-content
warnings are reported.

## Editing and removing

- In the panel, **Edit** renames the receiver and sets its people, and
  **Remove** deletes it. In Devices & services, **Reconfigure** renames it
  and **Configure** sets the people.
- Removing a receiver does not delete the script. If the script is still
  suitable, the receiver is offered again, unless you ignored it.
- If the script is deleted, the receiver is kept and shown as unavailable.
  Delivery fails with the reason in the [response](../services.md); other
  receivers are not affected. If the script returns, the receiver is
  reloaded at the next detection.
