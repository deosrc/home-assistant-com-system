# Getting started

This guide takes you from installing Com System to sending your first
notification. It needs Home Assistant 2026.10.4 or later.

## 1. Install

Com System is available in Home Assistant's marketplace.

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=deosrc&repository=home-assistant-com-system&category=integration)

Once it is added, check the integrations page for "Com System"
(**Settings > Devices & services**)

If not present, use **Add integration** and choose **Com System**.
This creates the hub which manages Com System. Only one hub can exist.

## 2. Add receivers

A receiver is a device or service Com System can send a notification to,
such as a phone or tablet running the Home Assistant app, an Echo, or a TV.

Com System finds supported receivers for you. After the hub is set up,
go to **Settings > Devices & services**. Receivers waiting to be added are
listed under **Discovered**. For each one, choose **Add**, or **Ignore** if
you never want it offered.

Nothing else is needed to get started:

- The **area** of a receiver is taken from its device in Home Assistant.
- The **person** of a mobile app is found from the user it is registered
  with.

We will explore receivers more later, but for now you just need one to send a
notification to.

## 3. Send a notification

The easiest way to send a notification is via the Com System UI. We will
explore this more later, but for now, select **Com System** from the sidebar
in Home Assistant, then go to **Test**.

A notification needs a message and at least one target:

- **People**: **Everyone**, or individual people. Receivers linked to those
  people are reached.
- **Receivers**: **All Areas**, or a selection of areas and named
  receivers.

IF your notification doesn't have an area or person it is assigned to (as is
the default for Persistent Notification), change **Target** to **Select**.

The For **Message**, click the **Add** button The default is for the message
to apply as text (e.g. the text of a mobile app notification), and
Text-to-speech (TTS) (e.g. read by an Amazon Echo). The receiver will chose
the most appropriate to use.

Everything else is optional and, asa a first test, it is recommend to keep
everything minimal to check the system is working. You can then experiment
more.

## Next steps

- [Dashboard](next-steps/dashboard.md): the panel, and the history of what
  was sent.
- [Receiver person](next-steps/person.md): choosing whose device a
  receiver is.
- [Receiver areas](next-steps/areas.md): how a receiver's area is found.
- [Channels](next-steps/channels.md): reusable notification defaults.
- [Receivers](receivers/README.md): what each receiver type supports.
