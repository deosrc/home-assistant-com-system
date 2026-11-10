# Persistent notification receiver

This receiver posts to the notification area in the Home Assistant
sidebar. Every user sees the same notifications, so it is not tied to a
person or device. It has no push behaviour, so it suits a record of last
resort.

## Setup

There is one receiver, offered as a discovery on **Settings > Devices &
services**. Choose **Add** to create it.

It starts with no person and no area, so it is **only used when named
explicitly** in the `receivers` target. If you give it a person or an area
(see [Receivers](README.md#people-and-areas)), person and area targets
reach it like any other receiver. See [Targets](../targets.md).

## Supported content

| Content | Supported |
| --- | --- |
| `message` | Yes |
| `title` | Yes |

## Behaviour

Delivery calls `persistent_notification.create`. It is create-only: each
notification creates its own entry in the notification area, and Com System
never replaces or dismisses one. Dismiss notifications in the Home
Assistant UI as normal.

## Example

```yaml
action: notify.com_system
data:
  title: Backup failed
  message: The nightly backup did not finish.
  receivers:
    active_choice: Select
    Select:
      entity_id: notification_receiver.persistent_notification
```
