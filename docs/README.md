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
3. Choose **Add integration** again to add a custom receiver. Once the hub
   exists, this flow adds receivers.

Discovery of built-in receivers, reconfiguration and options are stubs for
now and do nothing yet.

## Contents

- [Receivers](receivers/README.md): the receiver concept and custom
  receivers.

More documents (targets, content, conditions, actions and the UI) are added
as those features are built.
