# Dashboard and panel

Com System is designed to use native Home Assistant functionality where
possible, but given the complexity involved in sending notifications, it
also provides a user interface for composing, controlling, and diagnosing
issues.

To access it, select **Com System** from the Home Assistant sidebar. The
panel is for administrators only: it is hidden from other users.

## Dashboard

The dashboard gives a brief overview of the system. This is likely to change
so is not covered here in detail, and should be fairly self-explanatory.

When sources are waiting to be added, an alert at the top of the page says
how many, with a link to **Review in Devices & services**, as on the
Receivers page.

## Receivers

This allows gives you an overview of the configured receivers and a basic
status. Click a row to open the receiver's device page.

> [!NOTE]
> The reported status greatly depends on the implementation of the receiver.
> For example, WebOS TV receivers can report if the TV is online or not.
> The same is **NOT** available for mobile app receivers.

The switch for each receiver can be used to turn it on or off. This is
directly controlling the switch entity which Com System creates for each
receiver, so can also be controlled via automations if you wish.

The targets column will show the areas and people a receiver is assigned to.
If a receiver is not assigned, it will only be used if named explicitly.
For managing these settings, see [Areas](./areas.md) and [Person](person.md).

Conditions are only displayed as a count and a link as they are configured
within the options for a receiver config entry. For more details, see
[conditions](./../conditions.md).

When receivers are waiting to be added, an banner at the top of the page shows
how many, with a link to **Review in Devices & services** to add or ignore
them; see [receiver discovery](../receivers/README.md#automatic-detection).

Adding a custom or unsupported receiver is done by creating a script in a
specific format. **Check a script** below the table explains why a script
is or is not detected. See [custom receiver](../receivers/custom.md#checking-a-script)
for more details.

## Channels

Channels have two functions:

- To set the channel of a notification for the Android Home Assistant app
- To configure default properties for any notification using the channel

For example, you could create a channel for "Important" which sets the
priority and displays in Android Auto.

The channels page allows you to create, edit and delete [channels](channels.md).

Deleting a channel will also delete it from any connected Home Assistant apps.

## Recent

Often notifications may arrive at times when it is inconvenient to debug them.
The recent page keeps track of notifications which have been sent, what or who
they were targeting, and any warnings or errors which were raised.

By default, the last 200 notifications or 30 days will be kept, whichever is
smaller. To change them, open **Settings > Devices & services > Com System**,
choose the **Com System** hub entry and then **Configure**. The new limits apply
straight away and nothing is reloaded.

This page does not auto-update, so **Refresh** reloads the list.

When someone presses a notification action, the receivers table gains a
**Response** column indicating what action was pressed.

## Test

The testing tool sends a test notification and shows what happens. The form is
identical to the one in **Settings > Tools > Actions**, but with some
additional components to help see where a notification would be sent.

For an explanation of the options, see [services](./../services.md).

Below the form, **Receivers** updates as you change the targets, without sending
anything. Each matching receiver is `targeted`, or `skipped` with the reason
(it is disabled, or its [conditions](../conditions.md) did not pass or errored).
The conditions are evaluated with the content in the form.

Once ready, click **Send test** to call the notify action. A results panel will
appear below showing each receiver's outcome (delivered, failed or skipped) with
the reason and any warnings (content a receiver dropped), and the counts.

If nothing could be attempted, the error from the action is shown.

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
