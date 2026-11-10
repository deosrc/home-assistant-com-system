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
4. Choose **Add integration** again to add a
   [custom receiver](receivers/custom.md). Once the hub exists, this flow
   adds receivers.

Hub options are a stub for now and do nothing yet.

## Contents

- [Receivers](receivers/README.md): the receiver concept.
- [Custom receivers](receivers/custom.md): mapping a receiver to an action.
- [Targets](targets.md): how people, areas and receivers decide where a
  notification goes.
- [The notify.com_system action](services.md): sending a notification, its
  fields, delivery and the per-receiver response.
- [User interface](ui.md): the sidebar panel and its websocket commands.

More documents (rich content, conditions and notification actions) are added as those
features are built.
