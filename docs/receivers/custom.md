# Custom receivers

A custom receiver is a Home Assistant script. Com System detects suitable
scripts and offers each one as a receiver, like any other
[detected receiver](README.md#automatic-detection). You write the script, so
it can do anything Home Assistant can.

## Which scripts are detected

A script is offered only when it has a field named `notification` with the
**object** selector. It may have other fields, but they must all be
optional, because only `notification` is passed to the script. Scripts with
no `notification` field, another selector, or a required extra field are
ignored.

```yaml
fields:
  notification:
    selector:
      object: {}
    name: Notification
    required: true
sequence:
  - action: persistent_notification.create
    metadata: {}
    data:
      message: '{{ notification.message }}'
      title: '{{ notification.title }}'
```

Detection runs when the hub loads, after scripts are reloaded or added, and
once an hour. Choose **Add** on the discovery to create the receiver, or
**Ignore** to never be offered that script again.

## Checking a script

If a script you expected is not offered, use **Check a script** on the
panel's Receivers view. Choose the script and Com System reports:

- whether the script exists;
- whether it has a `notification` field using the object selector and no
  required extra fields, and what is wrong if not (no fields, a missing or
  misnamed field, the wrong selector, required extra fields);
- whether it is already a receiver, was ignored (delete the ignored entry in
  Devices & services to offer it again), or is waiting to be added.

When the script is fine and not yet known, **Rescan scripts** runs detection
now instead of waiting for the next one. The script is then waiting to be
added, as the alert at the top of the view shows.

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
