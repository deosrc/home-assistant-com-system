# Getting started

This guide takes you from installing Com System to sending your first
notification. It needs Home Assistant 2026.10.4 or later.

## 1. Install

Com System is available in Home Assistant's HACS marketplace.

1. Open the repository in the marketplace:
   [![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=deosrc&repository=home-assistant-com-system&category=integration)
2. Choose **Download**, then restart Home Assistant if asked.
3. Go to **Settings > Devices & services > Add integration** and choose
   **Com System**. This creates the hub. Only one hub can exist.

To install without HACS, copy `custom_components/com_system` into your
configuration directory and restart.

## 2. Add receivers

A receiver is a device or service Com System can send a notification to,
such as a phone or tablet running the Home Assistant app, an Echo, or a TV.

Com System finds them for you. After the hub is set up, go to **Settings >
Devices & services**. Receivers waiting to be added are listed under
**Discovered**. For each one, choose **Add**, or **Ignore** if you never
want it offered.

Nothing else is needed to get started:

- The **area** of a receiver is taken from its device in Home Assistant.
- The **person** of a mobile app is found from the user it is registered
  with.

The receiver types and how each is discovered are in
[receivers](receivers/README.md). Every receiver gets a device with a
**Notifications Enabled** switch and a read-only **Receiver** entity that
shows its last notification.

## 3. Send a notification

Open **Developer tools > Actions**, choose **Notify: Com System** and fill
in the form, or use the **Test** page of the Com System panel in the
sidebar, which shows who would receive the notification before you send it.

A notification needs a message and at least one target:

- **People**: **Everyone**, or individual people. Receivers linked to those
  people are reached.
- **Receivers**: **All Areas**, or a selection of areas and named
  receivers.

The content is the `message` (the display text) and an optional `title`. To
speak the message on a device that can, such as an Echo, give the message as
a list with a `tts` item.

```yaml
action: notify.com_system
data:
  title: Front door
  message:
    - type: text
      content: Someone is at the front door
    - type: tts
      content: Someone is at the front door
  people:
    active_choice: Individuals
    Individuals:
      - person.alice
  receivers:
    active_choice: Select
    Select:
      area_id: living_room
```

A receiver is used when it matches any target, so this reaches Alice's
phone, and any receiver in the living room. The action's response shows the
result for each receiver.

## Next steps

- [Dashboard](next-steps/dashboard.md): the panel, and the history of what
  was sent.
- [Receiver person](next-steps/person.md): choosing whose device a
  receiver is.
- [Receiver areas](next-steps/areas.md): how a receiver's area is found.
- [Channels](next-steps/channels.md): reusable notification defaults.
- [Receivers](receivers/README.md): what each receiver type supports.
