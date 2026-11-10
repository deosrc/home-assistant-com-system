# Custom receivers

A custom receiver delivers a notification by calling a Home Assistant action
(service) that you choose. Use one for anything that is not detected
automatically. The hub must exist first.

## Adding a receiver

Add one in either place:

- **Settings > Devices & services > Add integration > Com System**, or
- the **Com System** panel: **Receivers > Add custom receiver**.

Both use the same validation. The fields are:

| Field | Meaning |
| --- | --- |
| Name | Unique among receivers (ignoring case). |
| Action | The action, as `domain.action`, e.g. `notify.speaker`. Must exist. |
| Action data | The data sent to the action. Optional. |
| People | The people it relates to (panel; else use **Configure**). |

## Action data and templates

Action data is a mapping of fields to values. Every string in it, at any
depth, is a template. These variables are available:

| Variable | Value |
| --- | --- |
| `title` | The notification title, or none. |
| `message` | The notification message. |
| `priority` | The priority, or none. |
| `image` | The image, or none. |
| `data` | The notification's `data` block (empty when none). |

For example:

```yaml
message: "{{ title }}: {{ message }}"
data: "{{ data }}"
```

A custom receiver declares no capabilities, so it never reports
unsupported-content warnings. Templates are checked for syntax when you
save, not when they render.

## Editing and removing

- **Reconfigure** (the three dots menu in Devices & services) changes the
  name, action and action data. Receivers created from a discovery can be
  renamed.
- **Configure** (options) sets the people of any receiver.
- In the panel, **Edit** changes the same fields (action data as JSON) and
  the people of any receiver, and **Remove** deletes the receiver.

Saving reloads only that receiver.

## When delivery fails

If the action no longer exists, has no valid name, or its data cannot be
rendered, delivery to that receiver fails with the reason in the
[response](../services.md). If the action itself raises, that error is the
reason. Other receivers are not affected.
