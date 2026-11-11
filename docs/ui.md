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

A table of every receiver. The first column is a switch that turns the
receiver on or off; the other columns are its name, type and targets.
Targets are shown as badges, one for each area (with an area icon) and
person (with a person icon) the receiver is linked to, by name. A
receiver's area is the area of its device; change it in Home Assistant.

The switch operates the receiver's enabled switch, so it is the same as
using the switch entity or an automation, and the list updates when that
switch changes. It is disabled, and the row dimmed, for a receiver that is
unavailable (not loaded, or its source device is gone) or whose state
cannot be read.

Click a row (not its switch) to open the receiver's device page, where you
rename it, set its people or delete it (see
[custom receivers](receivers/custom.md#editing-and-removing)). Receivers
are added from discoveries; see [custom receivers](receivers/custom.md) for scripts.

**Check a script**, below the table, explains why a script is or is not
detected as a [custom receiver](receivers/custom.md#checking-a-script). You
choose the script with Home Assistant's entity picker (a plain list if the
picker is not available), and when it would be offered there is a **Rescan
scripts** button.

When sources are waiting to be added, an alert at the top of the view says
how many, with a link to **Review in Devices & services** to add or ignore
them; see [receiver discovery](receivers/README.md#automatic-detection). The
sources are not listed. A receiver with a type that is no longer known stays
in the list, with the type id as its type.

## Recent

The notifications sent, newest first, each with its title and message, the
time, and every receiver's result (delivered, failed or skipped) with the
reason and any warnings. The **Why** column says why the receiver was
included (see [Why a receiver was included](#why-a-receiver-was-included)).
**Refresh** reloads the list. Only the most recent notifications are kept;
see [history](history.md).

## Test

The testing tool sends a test notification and shows what happens.

- The form is Home Assistant's own action form, as on **Developer tools >
  Actions**, without the action picker. Enter an optional **title** and a
  **message**, and choose the targets: **Individuals** (one or more
  people) or **Everyone**, and **Select** (receivers, areas and so on) or
  **All Areas**. It starts with the defaults of the action (Everyone and All
  Areas), which Home Assistant reads from the action itself; untick a
  field to leave that group out, so it is not targeted. The groups are
  combined as in the [action](services.md#people). If Home Assistant has
  not loaded that form, the page says so.
- **Receivers reached** updates as you change the targets, without sending
  anything. Each matching receiver is `reached`, or `skipped` with the
  reason (it is disabled).
- **Send test** calls the [`notify.com_system` action](services.md), so it
  behaves exactly as an automation does, and may send real notifications.
  It is enabled once there is a message and at least one receiver would be
  reached. The result shows each receiver's outcome (delivered, failed or
  skipped) with the reason and any warnings, and the counts.
- If nothing could be attempted, the error from the action is shown.

## Why a receiver was included

The Test page (both tables) and the Recent page have a **Why** column of
badges, styled like the targets on the Receivers page. A receiver can have
several:

- **All Areas** or **Everyone**, when that choice matched it (the receiver's
  own area or person is then not listed);
- an **area** badge for the receiver's own area, when an area target
  matched it;
- a **person** badge for its own person, when that person matched it;
- **Named** when the receiver itself was selected, directly or through its
  device, or a label.

A receiver that matched more than one way shows each badge. Records saved
before this column existed show **None**.

## Websocket commands

The panel talks to Home Assistant through these commands. All require an
admin user.

- `com_system/ping`: returns `{"pong": true}`.
- `com_system/dashboard`: the counts shown on the dashboard.
- `com_system/receivers/list`: each receiver's name, type, enabled state,
  availability, switch entity id, `notification_receiver` entity id
  (`receiver_entity_id`), device id (`device_id`, the page a row opens),
  people, areas.
- `com_system/receivers/set_enabled`: turns the receiver's enabled switch on
  or off (`entry_id`, `enabled`).
- `com_system/scripts/check`: checks a script (`entity_id`) and returns
  `checks` (each `id`, `ok`, `message`) and `can_rescan`.
- `com_system/scripts/rescan`: runs detection now (needs the hub loaded).
- `com_system/discoveries/list`: the pending discoveries.
- `com_system/history/list`: the recent notifications, newest first
  (optional `limit`). Each has `id`, `time`, `notification` and `results`.
- `com_system/notify/preview`: the receivers the targets (`people` and
  `receivers`, as in the action) would reach, each `reached` or
  `skipped` with a reason. Sends nothing.
- `com_system/notify/test`: sends through the `notify.com_system` action
  (`message`, optional `title`, and the targets) and returns its response.
  A failure to send is the error `send_failed`.

## Installing the panel

The panel is written in TypeScript and is not committed in compiled form.
Releases attach `com_system.zip`, which HACS installs and which includes the
compiled panel. When running from a clone, build it first: see
[developing the panel](../README.md#developing-the-panel).
