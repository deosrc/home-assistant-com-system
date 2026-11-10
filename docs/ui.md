# User interface

Com System adds a **Com System** entry to the Home Assistant sidebar. The
panel is for administrators only: it is hidden from other users, and the
websocket commands behind it reject them with `unauthorized`.

## Dashboard

An overview of the receivers:

- **Receivers**: how many exist.
- **Enabled** and **Disabled**: by the state of each receiver's enabled
  switch. A receiver whose switch cannot be read is in neither.
- **Unavailable**: receivers that are not loaded or whose source device is
  gone. These also count as enabled or disabled.
- **Pending discoveries**: sources found by detection that are waiting to
  be added or ignored.
- **Receivers by type**.

## Receivers

A table of every receiver with its name, type, targets and status
(**Enabled**, **Disabled**, **Unavailable** or **Unknown**). Targets are shown
as badges, one for each area (with an area icon) and person (with a person
icon) the receiver is linked to, by name. A receiver's area is
the area of its device; change it in Home Assistant. Use **Enable** or
**Disable** to turn a receiver on or off. This operates the receiver's
enabled switch, so it is the same as using the switch entity or an
automation, and the list updates when the switch changes.

Below the table, **Pending discoveries** lists the sources waiting to be
added. Choose **Review in Devices & services** to add or ignore them; see
[receiver discovery](receivers/README.md#automatic-detection). A receiver
with a type that is no longer known stays in the list, with the type id as
its type.

## Websocket commands

The panel talks to Home Assistant through these commands. All require an
admin user.

- `com_system/ping`: returns `{"pong": true}`.
- `com_system/dashboard`: the counts shown on the dashboard.
- `com_system/receivers/list`: each receiver's name, type, enabled state,
  availability, entity id, people and areas.
- `com_system/receivers/set_enabled`: turns the receiver's enabled switch on
  or off (`entry_id`, `enabled`).
- `com_system/discoveries/list`: the pending discoveries.

## Installing the panel

The panel is written in TypeScript and is not committed in compiled form.
Releases attach `com_system.zip`, which HACS installs and which includes the
compiled panel. When running from a clone, build it first: see
[developing the panel](../README.md#developing-the-panel).
