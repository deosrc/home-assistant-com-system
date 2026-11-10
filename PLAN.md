# COM System – Home Assistant Custom Integration Plan

> Status: **Draft v0.1** – planning only, no code yet. This file is the
> source of truth for the design, the basis for the GitHub issues, and the
> context document for AI-assisted implementation. Sections marked **TBD**
> are intentionally unresolved.

## 1. Overview

COM System is a **notification distribution system** for Home Assistant,
built as a custom integration. It uses a **publish/subscribe** model:

- **Notification Receivers** are the subscribers. Each one represents
  something that can receive a notification.
- A notification is **published** by calling the `notify.com_system` action
  provided by this integration.
- COM System decides which receivers the notification applies to (based on
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

**Storage and discovery:**

- COM System has a single config entry, and each receiver is a **config
  subentry** of it. Receiver entities are derived from the subentries.
  Config subentries require a recent minimum Home Assistant version (to be
  verified; see section 8).
- Receivers are not created automatically. Where possible, COM System
  detects notification-capable devices and integrations that are already
  set up (e.g. a webOS TV, a mobile app device) and **offers to create a
  subentry** for each, which the user confirms. Whether Home Assistant's
  subentry flows can support such offers is **TBD**; the fallback is a
  "add receiver" flow that lists detected candidates.
- Custom receivers are always created manually.

### 2.2 Targets

Targets determine which receivers are triggered by a notification.

- **Specific receivers** – an option to name receivers directly.
- **People** – the main mechanism. Resolves to the receivers associated with
  those people.
- **Areas** – the main mechanism. Resolves to the receivers associated with
  those areas.
- **Default** – when no targets are specified, the notification goes to
  **all people and all areas**.

When several kinds of target are given, the results are combined as a
**union**: a receiver is used if it matches any listed person, any listed
area, or is named explicitly.

Only **enabled** receivers (section 2.4) are triggered, whichever way they
were targeted. A disabled receiver that is named explicitly is still
skipped. Skipped receivers are shown as skipped (disabled) in history and
in the testing tool.

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
    Initially the typed
    fields are **`priority`** (a normalised urgency level that each receiver
    type maps to its own mechanism) and **`image`** (an image URL or media
    reference). Others such as actions and sounds start in `data` and can be
    promoted to typed fields later if they prove widely used.
  - **Free-form `data`** – anything COM System does not support explicitly
    goes in a `data` object keyed by receiver type, e.g.
    `data: {mobile_app: {...}, pushover: {...}}`. Each receiver reads only
    its own block, so one notification can carry settings for several
    types. (Keying by type is an assumption from "mixed per-type blocks and
    typed fields"; to be confirmed.)

**Action responses:** each COM System notification is given an ID. When a
user responds to a notification action (e.g. presses a button on a mobile
app notification), COM System fires a `com_system_action` event (name
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
delivery result so they can be shown in the COM System UI (recent
notifications and the testing tool). Delivery is not treated as a failure.

### 2.4 Receiver entity and enabled state

Each Notification Receiver exposes an entity in a new
**`notification_receiver`** domain. A dedicated domain lets entity selectors
and select inputs be filtered to receivers only.

- The entity mimics a **switch**: state is `on` or `off`, where `on` means
  the receiver is currently **enabled** and `off` means disabled.
- The enabled state controls whether the receiver is triggered by
  `notify.com_system`. Disabled receivers are skipped during delivery.
- The state should survive restarts (restored on startup).
- Receivers must be **toggleable from the standard Home Assistant UI**
  (the entity's more-info dialog, and toggle controls on dashboard cards),
  not only through the COM System UI or actions.
- The domain provides actions to change the state:
  `notification_receiver.turn_on`, `notification_receiver.turn_off` and
  (as for switches) `notification_receiver.toggle`.
- Conditions such as do-not-disturb times are **not** built into COM
  System. They are created with ordinary Home Assistant automations that
  call these actions (e.g. turn a receiver off at 22:00 and on at 07:00).
  This keeps the integration simple and avoids duplicating scheduling
  features.

Standard UI requirement:

- The frontend decides which controls to show from the entity's domain, so
  an unrecognised `notification_receiver` domain may only get a generic
  more-info dialog with no toggle. This must be verified early.
- If the standard UI cannot toggle the entity, an alternative will be
  decided at that point. Candidates, to be evaluated then:
  - Expose the enabled state as a real `switch` entity instead (or as well),
    filtered by integration for selectors.
  - Keep the `notification_receiver` entity and add a companion `switch`.
  - Provide the toggle only in the COM System UI plus actions.

Implementation notes:

- Where possible, base the entity on Home Assistant's `ToggleEntity`
  and the `EntityComponent` pattern, so behaviour matches switches.
- The `notification_receiver` domain is provided by `com_system` itself
  (one integration, not a separate one).
- Whether a custom integration can cleanly register a brand-new entity
  domain (and its actions) is a risk to validate early. See section 8.

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
- How a COM System notification is translated into the underlying Home
  Assistant action call.
- How its receivers are associated with people and areas (section 2.7).

The **persistent notification** receiver posts to the notification area in
the Home Assistant UI (using the `persistent_notification` actions). Unlike
the other types it is not tied to a person or device: every user sees the
same notifications. It also has no push behaviour, so it suits a
record-of-last-resort. Its handling of content (e.g. a notification ID so a
notification can be replaced or dismissed) and its association with people
and areas are **TBD** (see section 2.7).

Receiver type definitions are written in code, and each declares its
capabilities: which typed fields and `data` keys it supports. Custom
(user-mapped action) receivers use a generic definition that declares no
capabilities. They receive the common content, `priority`, `image` and
their `data` block as variables for the mapped action, with no
unsupported-content warnings.

The custom (user-mapped action) receiver from section 2.1 remains the
fallback for anything not on this list. Further types can be added later,
so the type definition should be an extension point rather than hard-coded.

### 2.6 Notification conditions

Each receiver can be configured with **notification conditions**. They
decide, per notification, whether that receiver is used.

- Conditions use Home Assistant's built-in conditions system (the same
  format as automation and script conditions, including template, state,
  time and logical `and`/`or`/`not` conditions).
- Each condition is evaluated with the **notification details** supplied as
  variables, so conditions can inspect the notification. The exact variable
  shape is **TBD** (e.g. a `notification` object holding title, message,
  receiver-specific data and the requested targets).
- If the conditions do not pass, the receiver is skipped for that
  notification only. This is separate from the receiver's enabled state
  (section 2.4), which blocks all notifications.
- Example: skip a receiver when the notification message contains some
  given text, using a template condition on the notification variable.
- A receiver with no conditions always passes.

Evaluation order for a notification:

1. Resolve targets to receivers (section 2.2).
2. Drop receivers that are disabled (section 2.4).
3. Drop receivers whose conditions do not pass.
4. Deliver to the remaining receivers.

### 2.7 Associating receivers with people and areas

Targeting by person or area needs a way to decide which receivers belong to
whom. Each receiver type provides an association mechanism (part of the
receiver type definition, section 2.5), and users can override or extend it
manually on any receiver. Manual associations are stored as part of the
receiver's own configuration.

A receiver is associated with **at most one person**. A device used by
several people is treated as shared (see below) and reached through areas or
explicit targets. Whether a receiver can have more than one area is **TBD**.

**Mobile app (first implementation):**

- A mobile app device is normally associated with the Home Assistant user
  that is logged in to it, and so with the person linked to that user.
  (To be verified: the user and person link available from the mobile app
  registration and the person entity.)
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
- The default value, and whether it is guessed from the device, is **TBD**.

**Other receiver types:** the mechanism is TBD for each. For example, Alexa
devices and TVs are likely to be associated by area rather than by person,
while Pushover could be associated with a person manually. The persistent
notification receiver is system-wide, so it has no natural person or area;
how it takes part in person and area targeting is TBD.

**Areas:** a receiver can usually take its area from the underlying device
or entity in the Home Assistant area registry, with a manual override.

## 3. The `notify.com_system` action

- Provided by the integration and registered under the `notify` domain.
- Accepts the target parameters (section 2.2) plus the content parameters
  (section 2.3).
- Resolves targets to a set of receivers, drops disabled ones, drops those
  whose conditions do not pass, then delivers to each remaining receiver.
- Exact schema, response/return value and error handling: **TBD**.

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
  notification_receiver.py  # entity domain, entity class, on/off actions
  services.yaml / strings.json / translations/
  websocket_api.py  # commands backing the UI
  frontend/         # panel source and build output (TBD)
  (receiver registry, target resolver, dispatcher modules - TBD)
tests/
```

Core components (names provisional):

| Component | Responsibility |
| --- | --- |
| Receiver registry | Stores and manages configured receivers |
| Target resolver | Maps people, areas or receivers to a set of receivers |
| Receiver entity | `notification_receiver` entity holding enabled state |
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
- Recent notifications requires a history store; retention is **TBD**.
- The UI talks to the backend through Home Assistant's websocket API, which
  needs commands for receivers, history, resolution preview and test sends.

## 6. Standards and tooling (proposed, to be confirmed)

- HACS-compatible custom integration (`hacs.json`, `manifest.json`).
- UI config flow; no YAML-only configuration.
- Tests with `pytest-homeassistant-custom-component`.
- CI via GitHub Actions: hassfest, HACS validation, lint, tests.
- Follow Home Assistant developer docs and current core integration quality
  practices.
- Markdown files must pass the default markdownlint rules (including the
  80-character line limit).
- Documentation in `docs/` is maintained alongside the code (section 6.1).

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
  services.md           # notify.com_system, notification_receiver actions
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
- All documentation follows the markdownlint rule in section 6.

## 7. Proposed delivery phases (draft, to become GitHub issues)

Every phase includes updating the matching document(s) in `docs/`
(section 6.1) as part of its definition of done.

1. **Scaffold** – repository structure, manifest, HACS metadata, CI
   (including markdownlint), test harness, `docs/` skeleton and index,
   `CLAUDE.md` pointing to this plan and the documentation rule.
2. **Receiver model and storage** – data model, registry, persistence.
3. **Receiver entities** – `notification_receiver` domain, switch-like
   entity with restored state, `turn_on`/`turn_off`/`toggle` actions. Starts
   with a spike to validate registering a new domain and that the standard
   Home Assistant UI can toggle it; decide the alternative if not.
4. **Receiver config flow** – create/edit/remove receivers via the UI
   (built-in and custom action-mapped).
5. **Target resolution** – people, areas, explicit receivers,
   default-to-all behaviour, using each receiver's person and area
   associations (section 2.7).
6. **Notification conditions** – per-receiver conditions evaluated with the
   notification details, applied after target resolution and enabled state.
7. **`notify.com_system` action** – schema, wiring to resolver and
   dispatcher, delivery and error handling.
8. **Content parameters** – common content first, then receiver-specific
   content (e.g. mobile app actions) with per-receiver-type handling.
9. **Receiver types** – extensible type definition, then in priority order:
   mobile app (including person association and the personal/shared
   select), Alexa Media Player, persistent notification, Pushover, webOS TV,
   Music Assistant.
10. **History store** – persist recent notifications and delivery results.
11. **Websocket API** – commands for receivers, history, preview and test.
12. **UI** – panel shell and dashboard, then recent notifications,
   receivers, notification designer and testing tool.
13. **Documentation review and release** – review `docs/` for gaps, README,
    examples, HACS release.

## 8. Open questions

- What are the allowed `priority` values and how does each receiver type
  map them? What forms of `image` are accepted (URL, local media, camera
  entity)?
- Can `com_system` register a new `notification_receiver` entity domain
  (with its own actions) cleanly? To be settled by the phase 3 spike.
  Fallback: `switch` entities filtered by integration.
- Does the standard Home Assistant UI (more-info dialog, tile and entity
  cards) offer a toggle for a `notification_receiver` entity? If not, which
  alternative is chosen (see section 2.4)?
- Can config subentries be offered automatically for detected receivers
  (discovery), or only created from an "add receiver" flow that lists
  detected candidates?
- Should the entity expose attributes (type, associated people and areas,
  last triggered)?
- How are delivery failures reported (per receiver, aggregated, or
  fire-and-forget)?
- Frontend approach: custom panel built with Lit/web components, or other?
  Build and release process for the frontend assets.
- How much history is kept, where is it stored (HA storage or database),
  and is it configurable?
- Should the UI be admin-only, or visible to all users?
- How does each supported type deliver notifications: which actions or
  entities does it use, and how are its receivers discovered?
- Alexa Media Player is a non-native integration: how do we handle it being
  absent, and its differing action names across versions?
- Music Assistant announcements are not a notify action: how does the
  receiver model accommodate non-notify delivery mechanisms?
- What variables describe the notification to conditions (title, message,
  data, targets, resolved receiver), and are they stable enough to document?
- If a condition errors (e.g. a template fails), is the receiver skipped,
  used anyway, or is the error reported? Is it recorded in history?
- Where are conditions stored and edited: per receiver only, or can some be
  shared or global across receivers?
- Can conditions use the receiver's own context (e.g. its associated people
  or areas) as well as the notification details?
- Are the docs only read in the repository, or also published (e.g. GitHub
  Pages)? Affects link style and whether a site generator is needed.
- Should CI fail when code changes without a matching docs change, or is
  this left to review?
- How exactly is a mobile app device linked to a person (registration user
  versus the person's device trackers), and what if there is no person?
- What is the default for the personal/shared select, and can it be
  inferred (e.g. a tablet logged in as a kiosk user)?
- Can a receiver have more than one area?
- Should the personal/shared setting be generalised to all receiver types?
- How does the persistent notification receiver take part in targeting:
  only for the default (everyone) and explicit targets, or whenever any
  person or area is targeted? Can it be associated with a person to show the
  notification only to them (not supported natively)?
- Should persistent notifications be created with a stable ID so repeated
  notifications replace each other, and can the user dismiss them via COM
  System?
- Minimum supported Home Assistant version.
- Domain name and display name confirmation (`com_system` assumed).
