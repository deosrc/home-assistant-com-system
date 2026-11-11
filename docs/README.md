# Com System documentation

Documentation for the Com System integration. It is written alongside the
code and describes the integration as built. The development environment is
described in the [repository README](../README.md#development).

## Getting started

1. Install the integration (HACS custom repository, or copy
   `custom_components/com_system` into your configuration directory).
2. Go to **Settings > Devices & services > Add integration** and choose
   **Com System**. The first time, this creates the hub. Only one hub can
   exist.
3. Com System then looks for devices it can send notifications to and lists
   them under **Discovered** on the Devices & services page. Choose
   **Add** to create a receiver, or **Ignore** to never be offered it again.
   See [receiver discovery](receivers/README.md#automatic-detection).
4. To add your own receiver, write a
   [custom receiver script](receivers/custom.md); it is offered the same way.

The hub's options set how much [history](history.md) is kept.

## Contents

- [Receivers](receivers/README.md): the receiver concept.
- [Custom receivers](receivers/custom.md): scripts as receivers.
- [Mobile app receivers](receivers/mobile-app.md): delivery, the person
  link and personal or shared devices.
- [Targets](targets.md): how people, areas and receivers decide where a
  notification goes.
- [The notify.com_system action](services.md): sending a notification, its
  fields, delivery and the per-receiver response.
- [History](history.md): the recent notifications and their limits.
- [Content](content.md): priority, images, per-type `data`, capabilities
  and dropped content.
- [User interface](ui.md): the sidebar panel and its websocket commands.

More documents (conditions and notification actions) are added as those
features are built.
