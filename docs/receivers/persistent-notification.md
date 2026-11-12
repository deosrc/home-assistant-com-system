# Persistent notification receiver

This receiver posts to the notification area in the Home Assistant
sidebar. Every user sees the same notifications, so it is not tied to a
person or device. It has no push behaviour, so it suits a record of last
resort.

## Setup

There is one receiver, offered as a discovery on **Settings > Devices &
services**. Choose **Add** to create it.

It cannot relate to a person, so **Configure** has no people option and
person targets never reach it. It starts with no area, so it is **only
used when named explicitly** in the `receivers` target. If you give its
device an area (see [Receivers](README.md#people-and-areas)), area targets
reach it like any other receiver. See [Targets](../targets.md).

## Supported content

| Content | Supported |
| --- | --- |
| `message` | Yes |
| `title` | Yes |
| `priority`, `image`, `data` | No: dropped, with a warning |

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
