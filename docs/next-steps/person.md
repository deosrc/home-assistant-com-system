# Receiver person

A receiver can be assigned to one or more people so that it is automatically
used to notify them.

Sending a notification to **Everyone** reaches every receiver that has a
person, and **Individuals** reaches the receivers of the people you pick.

A receiver with no person is never reached by a people target, but can still
be reached by area or by name. See [targets](../targets.md).

How the person is set depends on the receiver type.

## Mobile app

The person for a mobile app notification receiver is determine automatically
via:

1. The person linked to the Home Assistant user the app is registered with.
2. Otherwise, the person whose device trackers include the app's device
   tracker.
3. Otherwise, no person.

### Personal or shared

Each mobile app receiver has a **Device use** option:

- **Personal**: the device is reached when its person is targeted.
- **Shared** (for example a wall tablet): the device has no person, so it is
  never reached by a person target. It is still reached by area or by naming
  it.

A new receiver starts as personal when a person is linked and as shared when
not. The choice is kept across restarts. 

To change the device use, go to **Settings > Devices & services > Com System**.
Then select the configure button for the device.

## Other receivers

Where a receiver cannot work out its person, such as Pushover, it can be set
manually.

go to **Settings > Devices & services > Com System**. Then select the configure
button for the device. Leave it empty if the receiver is not tied to anyone.

> [!NOTE]
> A person cannot be set for Persistent Notification or WebOS TV as these have no
> concept of a person/user.
