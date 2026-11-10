# Com System – Home Assistant Custom Integration Plan

> Status: **Draft v0.1** – planning only, no code yet. This file is the
> source of truth for the design of work not yet built, the basis for the
> GitHub issues, and the context document for AI-assisted implementation.
> Built features are removed from it (see section 7). Sections marked
> **TBD** are intentionally unresolved.

## 1. Overview

Com System is a **notification distribution system** for Home Assistant,
built as a custom integration. It uses a **publish/subscribe** model:

- **Notification Receivers** are the subscribers. Each one represents
  something that can receive a notification.
- A notification is **published** by calling the `notify.com_system` action
  provided by this integration.
- Com System decides which receivers the notification applies to (based on
  the target parameters) and delivers it to them.

The integration does not replace existing notification mechanisms. It sits in
front of them and routes notifications to the right ones.

## 2. Concepts

### 2.1 Notification Receiver

A Notification Receiver is a configured endpoint that can be triggered by COM
System. There are two kinds:

1. **Built-in receivers** for existing Home Assistant services and entities
   that can already receive notifications (e.g. `notify.*` services and
   notify entities, mobile app notify targets).
2. **Custom receivers** which are mapped to Home Assistant actions
   (services). This is similar to how the existing notifications system maps
   a notifier to a service call.

Each receiver needs (details **TBD**):

- A unique name/ID.
- The mechanism used to deliver to it (an existing service/entity, or a
  user-defined action mapping).
- Association data used for target resolution: which **people** and/or
  **areas** it relates to (section 2.7).

**Storage, discovery and settings:**

- Com System uses **one hub config entry** and **one config entry per
  receiver** (top-level entries, not subentries). Receiver entities are
  created by each receiver's own entry.
- The **hub** entry is created once by the user. It holds the
  integration-level settings (an options flow; initially the history
  retention limits) and starts detection. One hub is enforced in the config
  flow; the manifest does not use `single_config_entry`, which would block
  receiver entries. The user flow creates the hub if none exists, and once
  one exists it becomes "add a custom receiver".
- Integration-level parts (history store, the
  `notify.com_system` action, the websocket API and the panel) are set up
  once in the integration's `async_setup`, not per entry, so receiver
  entries can load in any order and without the hub. Settings are read at
  use time, so changing them does not reload receivers.
- Removing the hub removes the receiver entries it created (core offers no
  confirmation hook, see the spike #6 decisions below); removing a receiver
  entry removes only that receiver.
- Receivers of the built-in types are **offered as discoveries**. The hub
  detects notification-capable devices and integrations that are already set
  up (e.g. a webOS TV, a mobile app device) and raises a discovery flow for
  each, using a unique ID per source device so none is offered twice. The
  user confirms the discovery to create the receiver, or **ignores** it
  permanently. New receivers start enabled.
- A receiver that is deleted is offered again as a discovery on the next
  detection unless the user ignored it. To stop a receiver being used
  without deleting it, disable it with its enabled switch (section 2.4).
  Disabling the config entry itself removes the receiver's entities, so
  the documentation tells users to use the switch.
- When the underlying device or integration is removed, the receiver is
  **kept as unavailable**, with its conditions and settings, so it recovers
  if the device returns (after a reload that re-attaches it). Stale
  receivers are removed manually. Deliveries to an unavailable receiver fail
  with a clear per-receiver result.
- Custom receivers are always created manually, through the user flow, and
  edited through reconfigure and options flows.

**Spike #6 decisions** (verified with Home Assistant 2026.10.4; the feature
that builds on this removes it from the plan):

- **Discovery:** the hub raises an `integration_discovery` flow per source
  device with `unique_id` set to the source device (for example
  `<domain>_<identifier>`) and `_abort_if_unique_id_configured()`. Repeated
  detection does not duplicate a pending flow, a confirm-only `confirm` step
  creates the entry, and the core Ignore action works with no extra code
  (it removes the pending flow and stores an ignored entry that stops the
  device being offered again). Pending flows live in memory only, so
  "discoveries survive a restart" means the hub **re-detects on every
  setup**; configured and ignored devices are not offered again, and a
  deleted receiver is.
- **Attaching to another integration's device:** a device belongs to a single
  config entry and identifiers are unique per entry, so returning another
  integration's identifiers from `device_info` creates a **second** device
  (no area, no sharing). Instead, the receiver's entities set
  `self.device_entry` to the existing device (found with
  `async_get_devices(identifiers=...)`, using the source identifier stored in
  the receiver entry's data) and return no `device_info`. The entity
  registry then points at that device, so its area applies. Pre-creating the
  entity registry entry with a `device_id` does **not** work: the entity
  platform resets it to `None`. For types with no device, `device_info` with
  `(com_system, entry_id)` registers the receiver's own device.
- **Source removed:** removing the source integration deletes its device (our
  entry is not an owner) and the entity registry clears our `device_id`; the
  entities and the receiver entry remain. Availability is computed from
  whether the source device still exists, refreshed on device registry
  update events. When the device returns it is a new device, and our entities
  re-attach only when the receiver entry is **reloaded**, so the hub's
  detection must reload (or re-link) receivers whose source device
  reappears.
- **Switch state** is restored on restart with `RestoreEntity`.
- **Isolation:** an update listener that reloads only its own entry means
  editing one receiver leaves others untouched. Disabling a receiver's config
  entry does not remove its entities: they stay as `unavailable` (restored)
  with `disabled_by` set to the config entry, and other receivers are
  unaffected. This does not change the advice to use the enabled switch.
- **Hub removal cascade:** `async_remove_entry` on the hub can remove the
  receiver entries (schedule `config_entries.async_remove` as tasks) and
  their entities go with them. Core gives an integration **no hook to ask
  for confirmation** on removing an entry, so "after the user confirms" is
  not possible with the standard delete dialog; the documentation and the
  hub's title must warn that removing the hub removes all receivers.
- **Setup order:** `async_setup` runs once however entries load, so receiver
  entries load with or without the hub and in any order.

### 2.2 Targets

Targets determine which receivers are triggered by a notification.

- **Specific receivers** – an option to name receivers directly.
- **People** – the main mechanism. Resolves to the receivers associated with
  those people.
- **Areas** – the main mechanism. Resolves to the receivers associated with
  those areas.
- **Default** – when no targets are specified, the notification goes to
  **all people and all areas**. The persistent notification receiver is the
  exception: it is only used when named explicitly (section 2.5).

When several kinds of target are given, the results are combined as a
**union**: a receiver is used if it matches any listed person, any listed
area, or is named explicitly.

Only **enabled** receivers (the enabled switch, section 2.4) are triggered,
whichever way they were targeted. A disabled receiver that is named
explicitly is still skipped. Skipped receivers are shown as skipped
(disabled) in history and in the testing tool.

Open questions on target resolution are listed in section 8.

### 2.3 Message parameters

The `notify.com_system` action parameters fall into two groups:

1. **Target parameters** – described above.
2. **Content parameters** – describe what the notification says and how it
   behaves once delivered.

Content parameters are split into two tiers:

- **Common content** – supported by every receiver type: **`message`**
  (required) and **`title`** (optional). Receivers that have no title
  concept fold it into the message. Everything else, including priority and
  images, is receiver-specific.
- **Receiver-specific content** – only meaningful for certain receiver
  types, e.g. actions (buttons) on mobile app notifications. It is expressed
  in two ways:
  - **Typed fields** – commonly used parameters (used by several receiver
    types, or common in notification content) are explicit, validated
    top-level fields in the action schema. Receivers that do not support a
    typed field handle it as described under unsupported content below.
    Initially the typed fields are **`priority`** (a normalised urgency
    level that each receiver type maps to its own mechanism) and **`image`**
    (an image URL or media reference).
    - `priority` accepts `low`, `normal` (the default), `high` and
      `critical`. How each receiver type maps them is documented per type.
    - `image` accepts an http(s) URL, a local `/local/...` path or a media
      source ID. Camera entities are deferred.

    Others such as actions and sounds start in `data` and can be promoted
    to typed fields later if they prove widely used.
  - **Free-form `data`** – anything Com System does not support explicitly
    goes in a `data` object keyed by receiver type, e.g.
    `data: {mobile_app: {...}, pushover: {...}}`. Each receiver reads only
    its own block, so one notification can carry settings for several
    types. (Keying by type is an assumption from "mixed per-type blocks and
    typed fields"; to be confirmed.)

**Action responses:** each Com System notification is given an ID. When a
user responds to a notification action (e.g. presses a button on a mobile
app notification), Com System fires a `com_system_action` event (name
provisional) containing the notification ID, the receiver and the chosen
action, so automations can trigger on it. The response is also stored
against the notification in history, so the UI can show which receiver or
person responded. How each receiver type's native response event is mapped
to this event is documented per type. Responses from a type that has no
native response mechanism are not possible.

**Unsupported content:** when a notification carries content that a
resolved receiver does not support (e.g. mobile app actions sent to a
persistent notification), the notification is still delivered with the
content the receiver does support. The unsupported content is dropped and a
**warning is logged**. Warnings are recorded with the notification's
delivery result so they can be shown in the Com System UI (recent
notifications and the testing tool). Delivery is not treated as a failure.

### 2.4 Receiver entities and enabled state

Each Notification Receiver exposes two entities, which share the receiver's
device.

**Enabled switch (`switch` domain):**

- A standard Home Assistant `switch`. `on` means the receiver is
  **enabled** and `off` means disabled.
- The enabled state controls whether the receiver is triggered by
  `notify.com_system`. Disabled receivers are skipped during delivery.
- The state survives restarts (restored on startup).
- Being a real switch, it is toggleable from the standard Home Assistant UI
  (more-info dialog, cards) and uses the standard, described
  `switch.turn_on`, `switch.turn_off` and `switch.toggle` actions.
- Conditions such as do-not-disturb times are **not** built into Com
  System. They are created with ordinary Home Assistant automations that
  call these switch actions (e.g. turn a receiver off at 22:00 and on at
  07:00). This keeps the integration simple and avoids duplicating
  scheduling features.

**Receiver entity (`notification_receiver` domain):**

- A read-only entity in a new **`notification_receiver`** domain. The
  dedicated domain lets entity selectors and select inputs be filtered to
  receivers only. It is the entity named when a receiver is targeted
  explicitly.
- It is **modelled on Home Assistant's `event` entities**. The receiver
  entity **subclasses the core `EventEntity`** (spike #4 decision), which
  gives the timestamp state, `event_type` attribute, restore and
  `event_types` capability for free. A real `event` entity was considered,
  but a dedicated domain keeps selector filtering simple.
- Its **state** is the date and time of the last notification attempt for
  that receiver (an ISO 8601 timestamp), or `unknown` before the first.
- Like an event entity it also has an event type describing the delivery
  result (delivered, failed or skipped).
- Its **attributes** hold the content of that last notification (title,
  message, priority, image and data), any warnings, and the receiver's type
  and associated person and area. Exact attribute names are **TBD**, as is
  whether skipped notifications count as attempts.
- It provides **no actions**. Having no services in the new domain means
  Home Assistant has no service descriptions to look up for it (it can only
  load them from an integration of the same name, and none exists).

**Why two entities:** a new domain gives clean selector filtering, but the
Home Assistant frontend only offers toggle controls for a fixed set of
domains, and a separate integration for the domain is not possible because
HACS allows one integration per repository. Splitting the enabled state
into a real `switch` gets the full standard UI and described actions, and
keeps the new domain simple.

Implementation notes:

- The `notification_receiver` domain is provided by `com_system` itself
  (one integration, not a separate one). `async_setup` creates an
  `EntityComponent[EventEntity]` for the domain (stored in `hass.data`), and
  a receiver entry's `async_setup_entry` calls
  `component.async_setup_entry(entry)` directly, so the platform is
  `com_system/notification_receiver.py`. Do **not** use
  `hass.config_entries.async_forward_entry_setups(entry,
  ["notification_receiver"])`: it tries to set up an integration named
  `notification_receiver`, which does not exist, so it logs `Setup failed for
  'notification_receiver': Integration not found` and adds no entities
  (without raising). Unload with `component.async_unload_entry(entry)`.
- Known costs of the new domain (all harmless): Home Assistant logs one
  warning, `Failed to load integration for translation: Integration
  'notification_receiver' not found`, when the platform loads, and domain
  level translations (device class names and so on) do not exist. Entity
  level translations under `component.com_system.entity.notification_receiver`
  still work. `event` domain features keyed on the domain, such as the
  `event.received` automation trigger and the frontend's event more-info,
  do not apply; use state triggers on the timestamp state instead.
- Static attributes (receiver type, person, area) go in
  `extra_state_attributes`, which is not `@final`; `state`,
  `state_attributes` and `_trigger_event` are, so per-attempt content goes
  through the `event_attributes` argument of `_trigger_event`.
- The two entities, and the personal/shared select for mobile app
  receivers (section 2.7), are grouped on the receiver's device.
- The switch is the source of truth for enabled state; the receiver entity
  does not mirror it.

### 2.5 Supported receiver types

Initially supported receiver types, in priority order:

| Priority | Receiver type | Notes (to be verified) |
| --- | --- | --- |
| 1 | Mobile app | Core; per-device notify actions; rich content |
| 2 | Alexa Media Player | Non-native (custom); speech/announcements |
| 3 | Persistent notification | Core; HA UI notification area |
| 4 | Pushover | Core; priority, sound, attachments |
| 5 | webOS TV | Core; on-screen toast notifications |
| 6 | Music Assistant | Announcements via its own actions |

Each type needs a receiver-type definition (names provisional) covering:

- How receivers of that type are discovered and configured.
- Which common and receiver-specific content parameters it supports
  (section 2.3), i.e. its capabilities.
- How a Com System notification is translated into the underlying Home
  Assistant action call.
- How its receivers are associated with people and areas (section 2.7).

The **persistent notification** receiver posts to the notification area in
the Home Assistant UI (using the `persistent_notification` actions). Unlike
the other types it is not tied to a person or device: every user sees the
same notifications. It also has no push behaviour, so it suits a
record-of-last-resort. It has no person or area association and is used
**only when named explicitly** as a target, never by person or area targets
or by the default (everyone) target. It is create-only: each Com System
notification creates its own persistent notification (using the Com System
notification ID), and Com System never replaces or dismisses it. Users
dismiss notifications in the Home Assistant UI as normal.

**Delivery and discovery per type:**

- **Mobile app** – one receiver per registered device. Devices are detected
  from the mobile app integration's config entries and a discovery is
  offered for each. Delivery calls that device's `notify.mobile_app_<device>`
  action with the title, message and data (actions, image, channel and so
  on).
- **Alexa Media Player** (non-native integration) – one receiver per Echo
  device, detected from that integration's config entries and offered only
  when the integration is installed. Delivery calls the integration's
  `notify.alexa_media_*` action with announce/TTS data. If the integration
  later goes missing, the receiver shows as unavailable and deliveries to it
  fail with a clear per-receiver result. Exact action names and data are
  verified against the integration during implementation.
- **Persistent notification** – a single receiver (offered as a
  discovery like the others), used only when named explicitly. Delivery
  calls `persistent_notification.create` and is create-only (see section
  2.5).
- **Pushover** – one receiver per Pushover config entry (notify target),
  offered as a discovery. Delivery calls the Pushover notify action:
  `priority` maps to Pushover priority, `image` to an attachment, and other
  options (e.g. sound, URL) go in `data`. Pushover has no user link, so the
  person is chosen manually by editing the receiver.
- **webOS TV** – one receiver per webostv config entry, offered as a
  discovery. Delivery calls the TV's notify action (an on-screen toast:
  message only, with an optional icon in `data`). TVs are shared devices
  with no person; the area comes from the device registry.
- **Music Assistant** – one receiver per Music Assistant player, offered as
  a discovery. Delivery calls Music Assistant's announcement action rather
  than a notify action (the message is spoken; options such as an
  announcement URL or volume go in `data`). How a notification is delivered
  is an implementation detail of each receiver type's definition, so
  non-notify actions need no special handling in the receiver model. Players
  are shared devices with no person; the area comes from the device
  registry.

Receiver type definitions are written in code, and each declares its
capabilities: which typed fields and `data` keys it supports. Custom
(user-mapped action) receivers use a generic definition that declares no
capabilities. They receive the common content, `priority`, `image` and
their `data` block as variables for the mapped action, with no
unsupported-content warnings.

The custom (user-mapped action) receiver from section 2.1 remains the
fallback for anything not on this list.

### 2.6 Notification conditions

Each receiver can be configured with **notification conditions**. They
decide, per notification, whether that receiver is used.

- Conditions use Home Assistant's built-in conditions system (the same
  format as automation and script conditions, including template, state,
  time and logical `and`/`or`/`not` conditions).
- Each condition is evaluated with these variables:
  - `notification` – the notification details: ID, title, message,
    priority, image, `data` and the requested targets.
  - `receiver` – the receiver's own context: name, type, associated person
    and area, and entity ID.
  - `resolved_targets` – why the receiver matched: which person, area or
    explicit target selected it.
- Exact field names within these variables are **TBD** and will be
  documented in `docs/conditions.md`.
- If the conditions do not pass, the receiver is skipped for that
  notification only. This is separate from the receiver's enabled state
  (section 2.4), which blocks all notifications.
- Example: skip a receiver when the notification message contains some
  given text, using a template condition on the notification variable.
- A receiver with no conditions always passes.
- Conditions are stored and edited **per receiver only**, as part of its
  config entry's options. There are no global or shared condition sets.
- If a condition errors (e.g. a template fails to render), it is treated as
  not passed: the receiver is skipped, the error is logged, and the result
  is recorded as skipped (condition error) in history, the entity's last
  result and the testing tool. This fails safe for rules such as
  do-not-disturb.

Evaluation order for a notification:

1. Resolve targets to receivers (section 2.2).
2. Drop receivers that are disabled (section 2.4).
3. Drop receivers whose conditions do not pass.
4. Deliver to the remaining receivers.

### 2.7 Associating receivers with people and areas

Targeting by person or area needs a way to decide which receivers belong to
whom. Each receiver type provides an association mechanism (part of the
receiver type definition, section 2.5). Person associations can be
overridden manually on any receiver and are stored as part of the receiver's
own configuration. Areas are not set manually (see below).

A receiver is associated with **at most one person**. A device used by
several people is treated as shared (see below) and reached through areas or
explicit targets. A receiver has **at most one area**.

**Mobile app (first implementation):**

- A mobile app device is linked to a person in this order:
  1. The Home Assistant user the app is registered with, mapped to the
     person linked to that user.
  2. Otherwise, the person whose device trackers include the app's device
     tracker.
  3. Otherwise, no person: the receiver is effectively shared until the
     user sets a person manually.

  **Lookup procedure (spike #7, confirmed on Home Assistant 2026.10.4):**

  - The receiver's mobile app config entry (domain `mobile_app`) holds
    `data["user_id"]`, the Home Assistant user that registered the app. It
    is always present and is never edited, so it is the user to map from.
    The app's device has identifier `("mobile_app", data["device_id"])`
    and its device tracker has the entity registry unique ID
    `data["device_id"]` (platform `mobile_app`).
  - Step 1: find the `person.*` state whose `user_id` attribute equals the
    entry's `user_id`. The attribute is only present when the person is
    linked to a user, and a user can be linked to at most one person. This
    link is independent of the person's device trackers, so it keeps
    working if the tracker is removed from the person.
  - Step 2: if there is no match, call
    `homeassistant.components.person.persons_with_entity(hass,
    tracker_entity_id)`, which returns the `person.*` entity IDs whose
    `device_trackers` contain the tracker. Resolve the tracker with
    `entity_registry.async_get_entity_id("device_tracker", "mobile_app",
    data["device_id"])`. Normally this is `device_tracker.<device name>`
    but do not rely on that; the entity registry may rename it.
  - Step 3: if neither finds a person, there is no person (shared by
    default). Nothing else is available: the registration holds no person
    or name for the user beyond `user_id`.
  - Mobile app adds the tracker to the registering user's person only **at
    registration**, and only if a person is already linked to that user at
    that moment. A person created or linked later does not get the tracker,
    so step 2 alone misses that case; this is why step 1 comes first.
  - Step 2 can return several persons (a tracker may be listed on more than
    one). Take the first by entity ID order only as a tie-break and log it;
    the rule that a receiver has at most one person still applies.
  - Look up the device with
    `device_registry.async_get_device_by_identifier(("mobile_app",
    device_id), config_entry_id)`. `async_get_device` is deprecated in
    2026.10 and raises in tests (identifiers are no longer unique across
    config entries).
  - Removing the Home Assistant user removes the mobile app entry, so a
    receiver never points at a deleted user while its entry exists.
  - Resolve at use time (or on person and tracker registry changes), not
    once at discovery, because persons can be created, linked or edited
    afterwards. A manual person set on the receiver overrides all of this.
  - Verified with a throwaway test against a real `mobile_app`
    registration flow: user-linked person found (step 1) with the tracker
    also on the person; tracker removed from the person, step 1 still
    finds it; no user-linked person gives step 1 empty and step 2 empty,
    and after adding the tracker to a person manually step 2 finds it.
- Some devices are not personal: wall-mounted tablets and shared devices
  also run the mobile app. Notifying a person must not reach those.
- Each mobile app receiver therefore also exposes a **select entity** to
  define the device as **personal** or **shared**:
  - **Personal** – associated with its logged-in user's person and
    triggered when that person is targeted.
  - **Shared** – not associated with any person, so never triggered by a
    person target. It can still be triggered by area (e.g. the room it is
    in) or by naming it explicitly.
- Being a normal entity, the setting can be changed from the standard Home
  Assistant UI and by automations.
- The default is inferred from the person link: a newly detected device
  with a linked person starts as **personal**, and one with no linked person
  starts as **shared**. The user can change it at any time.

The personal/shared select applies to **mobile app receivers only**. Other
types already have a clear nature (see below).

**Other receiver types:** the mechanism is TBD for each. For example, Alexa
devices and TVs are likely to be associated by area rather than by person,
while Pushover could be associated with a person manually. The persistent
notification receiver is system-wide, so it has no person or area and is
only used when named explicitly (section 2.5).

**Areas:** a receiver's area is the area assigned to its device in the Home
Assistant device registry, and is dictated by that. There is no manual area
override in Com System: to change a receiver's area, change the area of the
device in Home Assistant. A receiver whose device has no area cannot be
reached by area targets.

For types with no natural device (Pushover, custom receivers, persistent
notification), each receiver creates its own device in the device registry
(e.g. "Pushover - Dale"), so the user can assign an area to it in the normal
Home Assistant UI. For types with an underlying device (mobile app, webOS
TV, Music Assistant players, Echo devices), the area comes from that
underlying device. Their receiver entities attach to that existing device
and do not register a separate Com System device.

## 3. The `notify.com_system` action

- Provided by the integration and registered under the `notify` domain.
- Accepts the target parameters (section 2.2) plus the content parameters
  (section 2.3).
- Resolves targets to a set of receivers, drops disabled ones, drops those
  whose conditions do not pass, then delivers to each remaining receiver.
- Delivery is independent per receiver: one receiver failing never blocks
  the others.
- The action returns **response data** listing each receiver's result
  (success, failed or skipped, with the reason and any warnings). Failures
  are also logged and recorded in history.
- The action itself only raises an error when nothing could be attempted
  (e.g. invalid input), not when individual receivers fail.
- Exact response format: **TBD**.

**Registration (spike #5, confirmed on Home Assistant 2026.10.4):**

- Register from `async_setup` with
  `hass.services.async_register("notify", "com_system", handler,
  schema=..., supports_response=SupportsResponse.OPTIONAL)`. It coexists
  with the core `notify` integration's own services and survives `notify`
  being set up afterwards. Use `OPTIONAL` so automations that ignore the
  response still work.
- Response data is returned by the handler as a dict and reaches callers
  via `return_response=True` (and `response_variable` in automations).
- UI metadata comes from `async_set_service_schema(hass, "notify",
  "com_system", {...})`, not `services.yaml`: the `notify` domain's
  `services.yaml` belongs to core, and the integration's own
  `services.yaml` is not read for it. The description gives `name`,
  `description` and `fields` with selectors, and HA adds the response
  marker itself. It appears in the `get_services` websocket result that the
  automation editor uses.
- `name` and `description` are plain strings set in code. They cannot be
  translated through `strings.json`, as translations for the `notify`
  domain's services belong to core.
- Targets: the `target:` selector in the description only supports entity
  and device filters (it always offers areas, floors and labels). It has no
  person concept. Use explicit fields instead: `person` (entity selector,
  `domain: person`, `multiple`), `area_id` (area selector, `multiple`) and
  `entity_id` (entity selector, `multiple`), plus `title` and `message`
  (text selectors).
- The schema is validated by the voluptuous schema passed to
  `async_register`; invalid input raises before the handler runs.
- Not verified: rendering in a real frontend (only the websocket
  description was checked).

## 4. Architecture (initial outline)

Proposed layout following Home Assistant custom integration conventions
(domain `com_system`):

```text
custom_components/com_system/
  __init__.py       # setup / unload, registers the notify action
  manifest.json
  config_flow.py    # config + options flow, receiver management
  const.py
  notify.py         # notify.com_system implementation
  notification_receiver.py  # read-only receiver entity (new domain)
  switch.py         # enabled switch entity
  services.yaml / strings.json / translations/
  websocket_api.py  # commands backing the UI
  frontend/         # panel source and build output (TBD)
  (target resolver, dispatcher modules - TBD)
tests/
```

Core components (names provisional):

| Component | Responsibility |
| --- | --- |
| Target resolver | Maps people, areas or receivers to a set of receivers |
| Receiver entities | Enabled switch and read-only `notification_receiver` |
| Condition evaluator | Runs a receiver's conditions against a notification |
| Dispatcher | Delivers to each resolved receiver, handling failures |
| Notify action | Entry point; validates input, calls resolver, dispatcher |
| Config/options flow | UI for creating and editing receivers |

The target resolver also applies the default of "everyone" when no targets
are given.

## 5. User interface

The integration provides its own UI inside Home Assistant (for example a
sidebar panel). Details of each view are **TBD**; the intended scope is:

| View | Purpose |
| --- | --- |
| Dashboard | Overview of the system's state and recent activity |
| Recent notifications | History of notifications sent and their delivery |
| Receivers | View, add, edit and remove configured receivers |
| Notification designer | Compose a notification (targets and content) |
| Testing tool | Send a test notification and see how it resolves |

Notes:

- The UI is a custom sidebar panel written as Lit web components in
  TypeScript, built with a bundler (e.g. Vite), following the Home Assistant
  frontend's own stack and reusing its components where possible.
- The panel is **admin-only**, and the websocket commands behind it require
  an admin user. It exposes notification contents, receivers and conditions
  and can send notifications, so it is not offered to non-admins.
- Only the frontend source is committed. CI builds the panel and the
  compiled bundle is attached to releases, which HACS installs from.
  Local development needs a build step (documented for contributors).
- The designer and testing tool both build on the `notify.com_system`
  action, so they must exercise the same code path as automations.
- Warnings about unsupported content are shown in recent notifications and
  the testing tool.
- The testing tool should show which receivers a notification would reach
  (target resolution) and the per-receiver outcome, including receivers
  skipped because they are disabled or a condition did not pass.
- The receiver editor needs a conditions editor. Home Assistant's condition
  selector can likely be reused.
- The designer must account for receiver-specific content (section 2.3),
  e.g. showing mobile app action options only when relevant.
- Recent notifications requires a history store. History is kept in Home
  Assistant's JSON storage (`Store`), capped by count and age (default to be
  chosen, e.g. last 200 notifications or 30 days, whichever comes first),
  and the limits are configurable in the integration options.
- The UI talks to the backend through Home Assistant's websocket API, which
  needs commands for receivers, history, resolution preview and test sends.

Decision from spike #8 (frontend panel build). The spike code is not merged;
the feature that builds the UI foundation recreates it:

- Layout: source in `frontend/` (Lit 3, TypeScript, Vite 6 library build).
  Output is one ES module, `custom_components/com_system/frontend/dist/
  com-system-panel.js`, gitignored and served at `/com_system_static/`.
- Registration: `panel_custom.async_register_panel` from `async_setup`, with
  `require_admin=True`; the manifest depends on `frontend`, `http`,
  `panel_custom` and `websocket_api`. Commands use `@require_admin`;
  verified in tests that a read-only user is rejected (`unauthorized`).
- Tests now need `home-assistant-frontend` (pinned to the version Home
  Assistant 2026.10.4 requires, 20260930.5) in `requirements-dev.txt`.
- Hot reload: setting `COM_SYSTEM_PANEL_DEV_URL` to the Vite dev server makes
  the panel load from it instead of the bundle. Home Assistant imports the
  module directly, so the source imports `/@vite/client` itself in dev mode
  (stripped from production builds). The devcontainer must forward port 5173
  as well as 8123. Verified in a browser: the panel renders, ping works, edits
  show without a manual refresh, and breakpoints hit the `.ts` source.
  A helper script that starts Home Assistant and Vite against a throwaway
  config made the checks repeatable and is worth recreating.
- Verified in a browser: the panel is hidden from non-admin users.
- Release: `release.yml` builds the bundle and attaches `com_system.zip` to
  the release; `hacs.json` uses `zip_release`. `frontend.yml` builds on PRs.
  The zip contents were checked locally; the release flow has not run.

## 6. Standards and tooling (proposed, to be confirmed)

- HACS-compatible custom integration (`hacs.json`, `manifest.json`).
- UI config flow; no YAML-only configuration.
- Tests with `pytest-homeassistant-custom-component`.
- CI via GitHub Actions: hassfest, HACS validation, lint, tests.
- Follow Home Assistant developer docs and current core integration quality
  practices.
- Markdown files must pass the default markdownlint rules (including the
  80-character line limit).
- Documentation in `docs/` is maintained alongside the code (section 6.1),
  and `AGENTS.md` records what agents and contributors need to know about
  features as built.
- Integration domain: `com_system`. Display name: "Com System".
- Minimum supported Home Assistant version: the latest stable release at the
  time of building. No compatibility shims for older versions; the minimum
  is raised when needed and recorded in `hacs.json`.

### 6.1 Documentation (`docs/` folder)

The repository maintains a `docs/` folder of user-facing documentation.
`PLAN.md` stays at the repository root as the design and AI context; `docs/`
describes the integration as actually implemented.

- Documentation is updated **as each part is implemented**. A phase or issue
  is not complete until its documentation is written or updated.
- Each topic has its own document. Proposed structure (names provisional):

```text
docs/
  README.md             # index and getting started
  targets.md            # people, areas, explicit receivers, defaults
  content.md            # common and receiver-specific content parameters
  conditions.md         # notification conditions and available variables
  services.md           # notify.com_system and receiver switch actions
  ui.md                 # dashboard, designer, testing tool, history
  receivers/
    README.md           # receiver concept, enabled state, entity
    custom.md           # custom (action-mapped) receivers
    mobile-app.md
    alexa-media-player.md
    persistent-notification.md
    pushover.md
    webostv.md
    music-assistant.md
```

- Each receiver document covers setup, supported content and capabilities,
  and examples. New receiver types add their own document.
- Documents include worked examples, such as a do-not-disturb automation
  using the receiver on/off actions.
- CI lints the markdown but does not enforce that docs change with code.
  The rule is upheld through a pull request template checklist, `CLAUDE.md`
  and review.
- The docs are read in the repository for now, but are written with
  GitHub Pages in mind: relative links between documents, one top-level
  heading per file, no reliance on GitHub-only rendering features, and a
  structure that a static site generator could publish unchanged. No site
  generator is set up initially.
- All documentation follows the markdownlint rule in section 6.

## 7. Delivery

Delivery is tracked as GitHub issues #1 to #29, grouped into milestones M0 to
M7. The issues, not this section, are the source of truth for order and
dependencies. In outline:

- **M0 Foundation** – dev environment with devcontainer and debugging,
  integration skeleton, test harness and CI.
- **M1 Spikes** – the new `notification_receiver` domain, the
  `notify.com_system` action, the hub entry and discovery flows, the mobile
  app person link and the frontend panel build.
- **M2 Core** – receiver model, entities, detection, UI foundation, target
  resolution, the action with a testing tool, mobile app and custom
  receivers (basic notifications: message and title).
- **M3 Receiver types** – persistent notification, Alexa Media Player,
  Pushover and webOS TV.
- **M4 History and rich content** – history, content parameters and the
  designer, mobile app actions and responses.
- **M5 Conditions** – a spike, then notification conditions.
- **M6 Catch-all and release** – rolling UI and documentation tickets, then
  the first release.
- **M7 After first release** – the Music Assistant receiver.

Documentation and UI are delivered with each feature, not as separate
phases. When a feature is complete it is **removed from this plan**: it is
documented in `docs/` and covered in `AGENTS.md`, so this file only describes
work still to do. When the last item is done, this file can be deleted.

## 8. Open questions

- Which Integrations-page titles keep 10 to 30 receiver entries readable?
