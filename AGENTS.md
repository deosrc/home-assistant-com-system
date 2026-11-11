# Agent and contributor notes

Read [PLAN.md](PLAN.md) for the design of work not yet built. This file
records the conventions and how things work as built.

## Rules

- Ship documentation (`docs/`, and the README where relevant) and UI with
  each feature, not as a later step.
- Update this file when behavior or architecture changes.
- When a feature is complete, remove it from `PLAN.md`.
- Markdown must pass `npm run lint:md` (default rules, 80 columns).

## Dev environment

- Work in the devcontainer. See the
  [README](README.md#development) for starting Home Assistant, debugging,
  tests and linting.
- The integration lives in `custom_components/com_system/` and is symlinked
  into `config/custom_components/` by `scripts/setup`.
- `config/configuration.yaml` is the only committed file under `config/`.

## Commands

- Start Home Assistant: `scripts/develop` (or the **Start Home Assistant**
  task). Debug with the **Home Assistant: attach** launch config.
- Test: `python3 -m pytest tests`. Tests use
  `pytest-homeassistant-custom-component`; `tests/conftest.py` enables
  custom integrations for every test.
- Lint Python: `ruff check .` and `ruff format --check .` (format with
  `ruff format .`). Ruff is configured in `pyproject.toml`.
- Lint Markdown: `npm run lint:md`.
- Icon: `custom_components/com_system/brand/` holds `icon.png` (256 px) and
  `icon@2x.png` (512 px) on a transparent background; Home Assistant serves
  them without the brands repository. The source is `assets/icon.svg`. To
  regenerate, render it to PNG at those widths (for example with
  `@resvg/resvg-js`).
- Panel (in `frontend/`): `npm run lint`, `npm test`, `npm run build`.
  Hot reload: `scripts/develop` starts Vite and sets
  `COM_SYSTEM_PANEL_DEV_URL` (opt out with `COM_SYSTEM_PANEL_BUNDLE=1`);
  `scripts/develop-frontend` does it on a throwaway config.

## Architecture as built

- Domain `com_system`. The manifest does not use `single_config_entry`
  because receivers are separate config entries.
- One hub entry (`entry_type: hub`) and one entry per receiver
  (`entry_type: receiver` for receivers created from a discovery, and
  the legacy `custom_receiver`; both are in `RECEIVER_ENTRY_TYPES`); see
  `const.py`.
- Receiver entry data: `entry_type`, `receiver_type` (missing means
  `custom`), `name`, optional `source_id`. Options: `people` (`person.*`
  entity ids). Entries are the only storage. There is no stored area: a
  receiver's area is the area of its `notification_receiver` entity, which is
  its device's (`ReceiverRegistry.areas_of`; the switch's area is ignored),
  so it is changed in Home Assistant, not in Com System.
- Custom receivers are scripts (type id `custom`, name "Script").
  `CustomReceiverType` in `receiver_type.py` detects them: a script whose
  service description (`async_get_all_descriptions`) has a `notification`
  field with an `object` selector and no other required field
  (`is_notification_script`). The
  source id is the script's object id; availability is whether the
  `script.<id>` service exists. Delivery calls `script.<id>` (blocking) with
  `{notification: {title, message, ...}}`, the whole notification; a missing
  script raises so the dispatcher reports `failed`. The detector also runs
  (debounced) on `service_registered` / `service_removed` for the `script`
  domain. See `docs/receivers/custom.md`. Entries made by earlier builds
  with entry type `custom_receiver` and no source id are listed as
  unavailable.
- `receiver.py`: frozen `Receiver` dataclass built by `Receiver.from_entry`.
- `receiver_type.py`: `ReceiverType` is the extension point (id, name,
  capabilities, `async_deliver`, association hooks, `async_detect`,
  `is_source_available`, `discoverable`). Subclass it and call
  `register_receiver_type()` to add a type; ids are unique.
  `CustomReceiverType` is the generic type. `async_deliver(hass, receiver,
  notification)` returns a list of warnings (content the type dropped) and
  raises to report a failure; the base class raises `NotImplementedError`,
  which the dispatcher reports as a failed result. The custom, persistent
  notification, mobile app, Pushover, webOS TV and Alexa Media Player types
  deliver so far; each
  other built-in type's own feature implements it.
  `associated_people(hass, receiver)` takes `hass` so a type can look people
  up at use time.
- `builtin_types.py`: the six built-in types (mobile app, Alexa Media
  Player, persistent notification, Pushover, webOS TV, Music Assistant),
  registered in `async_setup`. They have detection; delivery is added by
  each type's own feature (the persistent notification, mobile app,
  Pushover, webOS TV and Alexa Media Player types have it).
  `PersistentNotificationReceiverType.async_deliver` calls
  `persistent_notification.create` (blocking) with `message` and, when
  given, `title`, and never sends `notification_id`: HA then generates one,
  so every notification is its own and Com System never replaces or
  dismisses it. It declares no capabilities and returns no warnings. It sets
  `supports_people = False` on `ReceiverType` (default True): the options
  flow then shows an empty `no_options` step instead of the people field,
  and `associated_people` returns nothing even if people were stored. The
  action's fields were checked against HA 2026.10. Com System has no
  notification ID yet; when it does, pass it as `notification_id` (create
  would then replace a notification with the same id).
  `DeviceReceiverType` offers one receiver per device of `source_domain`
  (source id is the device identifier in that domain, and the receiver's
  entities attach to that device via
  `source_device_identifiers`); `EntryReceiverType` offers one per config
  entry (source id is its unique id, else its entry id; no source device, so
  entities get their own). To add a built-in type, subclass one, set
  `type_id`, `name`, `source_domain`, and add it to `BUILTIN_RECEIVER_TYPES`.
  The Music Assistant device identifiers are assumed to be
  `(domain, <player id>)` and were not checked against the integration.
  `AlexaMediaReceiverType` (a `DeviceReceiverType`, domain `alexa_media`,
  checked against the integration's source): the Echo's device identifier is
  `("alexa_media", <unique_id>)`, which is the serial number (for a second
  account it is a slug of serial and email). Delivery calls the single
  `notify.alexa_media` action (the integration registers it for all devices)
  with `target: [source_id]`, `type: announce`, `message` and optional
  `title`; it fails if the action is missing. The integration silently skips
  an offline Echo (Com System reports delivered) and, for `announce`, only
  matches the serial, so a second account's devices are skipped. Availability
  is the device being in the registry. The type keeps the people option
  (nothing links an Echo to a person); its area is its device's. Capabilities
  are `title`. See `docs/receivers/alexa-media-player.md`.
- `pushover.py` and `PushoverReceiverType`: one receiver per device
  (target) of each loaded `pushover` config entry. The source id is
  `<entry unique id or entry id>:<device>`. Core's integration does not
  expose devices, so `async_entry_devices` calls the entry's
  `runtime_data.api.validate(user_key)` in the executor (Pushover's
  validate response lists `devices`); an entry that is not loaded or a
  failing call offers nothing. Availability is whether the entry exists.
  Delivery calls `notify.<slugify(entry.data["name"])>` with `message`,
  `title` when given and `target: [device]` (fails if the action is
  missing). Core registers that action when it loads the notify platform
  with the entry's name; it takes `message`, `title`, `target` and `data`.
  Checked against Home Assistant core source (not run). `data` keys:
  `priority` (-2 to 2, Pushover's own), `attachment` (a local file path
  inside `allowlist_external_dirs`, not a URL), `url`, `url_title`, `sound`,
  `html`, `timestamp`, `ttl`, `retry`, `expire`, `callback_url`, `tags`.
  Later `priority` should map low/normal/high/critical to -1/0/1/2 (2 needs
  `retry` and `expire`), and `image` must be resolved to a local allowed
  path for `attachment`; neither is built. The person is chosen manually
  (people option; `supports_people` is True). Entities get their own device
  (no source device), so the area is set on that device.
- `mobile_app.py` and `MobileAppReceiverType`: delivery calls
  `notify.mobile_app_<slugify(device_name)>` with `message` and `title`
  (fails if the action is missing). The source entry is the `mobile_app`
  config entry whose `data["device_id"]` is the receiver's source id.
  `linked_person` resolves the person at each call: the `person.*` state
  whose `user_id` is the entry's `user_id`, else
  `persons_with_entity` for the tracker (first by entity id). People are
  none when shared, else the linked person (the type has
  `supports_people = False`, so there is no people option and a stored one
  is ignored). `select.py` is the `audience` select (`personal`/`shared`,
  mobile app receivers only, `RestoreEntity`, the source of truth; the
  default is personal if a person is linked, else shared). Until it is loaded
  `audience_of` infers the default. The panel does not show or edit it: it is
  changed on the entity. Platforms are `PLATFORMS` in `__init__.py`.
- `webostv.py` and `WebOSTVReceiverType` (an `EntryReceiverType`): delivery
  calls `notify.<slugify(config entry title)>` (the legacy notify platform
  the integration loads by discovery, named from the title at setup time)
  with `message` and, if `notification["data"]["icon"]` is set,
  `data: {icon}`; those are the only keys the integration reads (checked
  against HA 2025.1 source), so the title is dropped with a warning. The
  integration logs rather than raises when the TV is unreachable, so that is
  reported as delivered. The source id is the entry's unique id, which is
  also the TV's device identifier `(webostv, id)`, so
  `source_device_identifiers` attaches the entities to that device and the
  area is the TV's. `supports_people = False`. The `data` key is not in the
  `notify.com_system` schema yet; the icon is tested through the delivery
  function.
- `detection.py`: `ReceiverDetector` is created by the hub entry's setup
  (`entry.runtime_data`). It detects once Home Assistant has started, after
  device registry changes (debounced) and hourly. For each candidate it
  calls `flow.async_init` with source `integration_discovery`; the flow's
  unique id is `<type_id>_<source_id>` (`discovery_unique_id`). Candidates
  whose unique id is an existing entry (configured or ignored) are skipped,
  so a deleted receiver is offered again and an ignored one is not. A
  receiver whose source is gone is never removed; the detector tracks
  availability via `is_source_available` and reloads the entry when its
  source returns. Entities (later) must derive availability from the same
  method.
- `registry.py`: `ReceiverRegistry` reads receivers from the config entries
  on each call, so it is always current and needs no hub or load order. It
  is created once in `async_setup` as `hass.data[DOMAIN]["registry"]`.
  Unknown types stay listed (`type_of` returns `None`).
- Each receiver entry has two entities on one device, set up in
  `async_setup_entry` (the hub has none): the enabled `switch`
  (`switch.py`, named "Notifications Enabled", `RestoreEntity`, on by
  default, the source of truth for
  enabled) and the read-only `notification_receiver` entity
  (`notification_receiver.py`, subclasses `EventEntity`; event types
  `delivered`, `failed`, `skipped`). The switch and the mobile app select
  have `EntityCategory.CONFIG`. All derive from `ReceiverEntity`
  (`entity.py`), which builds the device (`(com_system, entry_id)`), or
  attaches to the source device returned by
  `ReceiverType.source_device_identifiers`, and registers the entity in
  `hass.data[DOMAIN]["entities"][entry_id][entity_key]`
  (`enabled`, `receiver`). Delivery records an attempt with
  `NotificationReceiverEntity.async_record_attempt(result, notification,
  warnings)`; the attributes are `title`, `message`, `priority`, `image`,
  `data`, `warnings` plus `receiver_type`, `people` and `areas` (the device's area).
- The `notification_receiver` domain is provided by this integration:
  `async_setup` creates an `EntityComponent` in
  `hass.data[DOMAIN]["notification_receiver_component"]` and the entry calls
  `component.async_setup_entry(entry)` itself. Do not forward the entry to
  `notification_receiver` with `async_forward_entry_setups` (it is not an
  integration, so that fails silently). Home Assistant logs one harmless
  translation warning for the domain. Editing a receiver reloads only that
  entry.
- `config_flow.py`: the user step creates the hub if none exists, otherwise
  it aborts `receivers_are_discovered` (receivers come from discoveries). One
  hub is enforced there. The options flow of a receiver edits its people; the hub's
  options flow edits the history limits. `integration_discovery` aborts with
  `not_available` without a hub or a known type, otherwise sets the unique
  id, aborts if configured and shows a confirm-only `confirm` step that
  creates the receiver (core's Ignore needs no code). Reconfigure renames a
  receiver; the hub aborts `not_implemented`.
- `__init__.py`: `async_setup` registers the built-in types and creates the
  registry and the component; setting up the hub starts the detector;
  receiver entries set up and unload their entities.
- `panel.py`: registers the admin-only sidebar panel with `panel_custom`
  (`require_admin=True`) from `async_setup`. The bundle is served from
  `custom_components/com_system/frontend/dist/` at `/com_system_static/`; if
  it is missing a warning is logged and the panel does not load (tests run
  without a build). `COM_SYSTEM_PANEL_DEV_URL` loads the panel from the Vite
  dev server instead. The manifest depends on `frontend`, `http`,
  `panel_custom` and `websocket_api`, and tests need `home-assistant-frontend`
  (pinned in `requirements-dev.txt` to what Home Assistant requires).
- `targets.py`: `resolve_targets(hass, people=, areas=, receivers=)` returns
  `ResolvedTargets(receivers, skipped)` (sorted by name). Union of people,
  areas (`ReceiverRegistry.people_of` / `areas_of`) and named receiver entry
  ids; a group that is not given is not targeted, so no targets at all match
  nothing (there is no default). There is no per-type exclusion: the
  persistent notification receiver has no area until its device gets one,
  so it matches only when named, but then area targets reach it. It never
  has a person (see `supports_people`). Disabled receivers (the enabled
  switch entity in `hass.data[DOMAIN][DATA_ENTITIES]`, or not loaded) go to
  `skipped` whichever way they matched. See `docs/targets.md`.
- `notify.py`: registers `notify.com_system` from `async_setup`
  (`supports_response=OPTIONAL`) with a voluptuous schema (`message`,
  `title`, `people`, `receivers`; title is first, which sets the order in
  the form) and its UI description through
  `async_set_service_schema` (the `notify` domain's `services.yaml` is
  core's, so the integration's `services.yaml` is deliberately empty (hassfest
  requires the file); name and description are plain strings). `people` and
  `receivers` are `choose` selectors whose choice names are the labels the
  form shows, because the selector has no label
  field and the notify domain's translations are core's: `people` is
  `Individuals` (entity selector) or `Everyone`, `receivers` is `Select`
  (a `target` selector limited to `notification_receiver` entities of this
  integration) or `All Areas`. The first choice is what the form shows for
  an unset field, so the panel always sends a value. The value is
  `{active_choice, <choice>: value}`; `validate_people` and
  `validate_receivers` normalise it (a plain person or list means
  individuals, a plain target dict means Select) and `resolve_targets` takes
  `all_people` and `all_areas`. `_select_targets` turns a Select target into
  areas (area ids, and the areas of floors, so area rules apply) and named
  receivers (receiver entities, plus the receiver entities Home Assistant's
  `async_extract_referenced_entity_ids` finds for devices and labels).
  Receiver entities are mapped to entry ids through the entity registry;
  ones that are not Com System's match nothing. A call with neither
  `people` nor `receivers` raises "No targets given", and the panel leaves
  an unticked field out of the data.
  `async_send` resolves, dispatches and returns `{results, counts}`; it
  raises `ServiceValidationError` only when no enabled receiver matched
  (none, or all disabled). The websocket test send calls the action through
  `hass.services`, so UI and automations share one path.
- `dispatcher.py`: `async_dispatch(hass, resolved, notification)` delivers
  to the enabled receivers concurrently (`asyncio.gather`); `_deliver`
  never raises, so one failure cannot affect another (unknown type,
  `NotImplementedError` and any exception become `failed` results with a
  reason). Disabled receivers become `skipped`. Every result, including
  failed and skipped, is recorded with `async_record_attempt` (so skipped
  attempts do update the receiver entity). Results are
  `ReceiverResult(receiver, type_name, result, reason, warnings)`, ordered by
  name; `result` is one of `RESULTS` (`delivered`, `failed`, `skipped`).
  Conditions are not evaluated yet.
- `history.py`: `NotificationHistory` (`hass.data[DOMAIN][DATA_HISTORY]`,
  created in `async_setup`) keeps records newest first in a `Store`
  (`com_system.history`, saved with a delay). A record is `{id, time,
  notification, results}`, results being `ReceiverResult.as_dict()`
  (including warnings). `ResolvedTargets.reasons` (by entry id) and
  `ReceiverResult.reasons` say why a receiver was included: `everyone` / `all_areas`
  when those choices matched it, else the receiver's own `person`/`area`
  that matched, and `receiver` when named; the preview
  command and the action response carry them, and the panel's `reasons.ts`
  renders them as badges. `async_dispatch` records every send, after feeding
  each receiver entity's last attempt. The limits are the hub entry's
  options `history_max_count` (default 200) and `history_max_age_days`
  (default 30), read by `limits()` each time, so the hub has no update
  listener and nothing reloads. Pruning happens on record and on list.
  `async_last_attempt(entry_id)` finds a receiver's latest result. The hub's
  options flow edits the limits. Docs: `docs/history.md`.
- `websocket_api.py`: the commands behind the panel
  (`com_system/ping`, `dashboard`, `receivers/list`, `receivers/set_enabled`,
  `scripts/check` (`_script_checks`: why a script is or
  is not a receiver, built on `notification_script_problems`; `can_rescan`
  is false when registered, ignored or already pending) and
  `scripts/rescan` (calls the hub detector's `async_detect`),
  `discoveries/list`, `history/list`, `notify/preview`, `notify/test`).
  Every command must have `@websocket_api.require_admin`;
  `tests/test_panel.py` checks all of them reject a read-only user. They read
  the registry and config entries (`areas` come from
  `ReceiverRegistry.areas_of`); enabling or disabling calls the receiver's
  switch service, so the switch stays the source of truth. Pending
  discoveries are the `integration_discovery` flows in progress. Add new
  commands to `async_register_commands` and to `COMMANDS` in the test.
- `frontend/`: the panel source (Lit 3, TypeScript, Vite 6, Vitest, ESLint).
  `com-system-panel.ts` is the shell and navigation (routes `dashboard`,
  `receivers`, `history` and `test` under `/com-system/`), `api.ts` wraps the websocket
  commands (`ComSystemApi`), and each view is its own element
  (`dashboard-view.ts`, `receivers-view.ts`, `test-view.ts`); the first two
  refetch when switch states change. `test-view.ts` is the testing tool: it
  previews with `notify/preview` on every target change and sends with
  `notify/test`. The form is Home Assistant's `ha-service-control` with
  `hide-picker hide-description` and `.value` set to
  `{action: "notify.com_system"}` with no `data` at first, so the form
  applies the `default` of each field from the action description (as when
  an action is picked in Developer tools; this relies on the form loading
  defaults only when the value has no `data` key, so never seed `data`); its
  `value-changed` `detail.value.data` holds `title`, `message`,
  `people` and `receivers` (choose values: when the user flips the choice
  the other choice's value stays in the object, so read `active_choice`
  first; the Select value is a target with any of `entity_id`, `area_id`,
  `device_id`, `floor_id`, `label_id`, all kept and sent), which are the
  preview and send fields. The view holds no defaults of its own; they live
  in `SERVICE_DESCRIPTION`. The form reads the fields from `hass.services`
  (our
  `async_set_service_schema` description), is an internal element that HA
  loads lazily, and its loading from a custom panel is unverified in a real
  frontend; the view waits `controlTimeoutMs` for it and otherwise shows an
  error. Lit in jsdom drops template expressions that are the last thing in
  a template (the response card), so `test-view.ts` wraps them in a `div`;
  keep a wrapper if you add a trailing expression. The cards copy Developer tools
  > Actions: `ha-card` with `.card-header` (title and a `.secondary` line),
  `.card-content` and `.card-actions` (button right-aligned, an
  `ha-progress-button raised` when HA has loaded it, else a native button).
  Avoid a `title` property on elements: it clashes with `HTMLElement.title`.
  `receivers-view.ts` uses `ha-card` sections like the test view, an
  `ha-alert` for pending discoveries (count and link, no list), an
  `ha-entity-picker` for the script check (a native select when it is not
  defined). A receiver row opens its device page (under
  `/config/devices/device/`, via `history.pushState` and `location-changed`); editing
  and deleting happen there and in the config flows, not in the panel. An
  expression at the very start of a template needs a wrapper `div` like
  trailing ones. Add views by adding an element, an entry in `VIEWS` and a
  command. Elements use `static properties` and `declare` fields (no
  decorators). The build is one ES module and the HMR client is imported
  only when the mode is `development`. Commands: `npm run lint`,
  `npm test`, `npm run build` in `frontend/`; `scripts/develop` for hot reload.
- Strings live in `strings.json`; `translations/en.json` is a copy and must
  be kept in step.
- `hacs.json` records the minimum Home Assistant version; keep it in step
  with `requirements-dev.txt`.

## CI

GitHub Actions workflows in `.github/workflows/` run on pull requests and
pushes to `main`: `lint.yml` (Ruff check and format), `tests.yml` (pytest on
Python 3.14), `frontend.yml` (panel lint, test and build),
`markdownlint.yml`, `hassfest.yml` and `hacs.yml` (HACS
validation). Hassfest and HACS validation also run nightly. All must pass.

`release.yml` is not a check. When a release is published it builds the
panel and attaches `com_system.zip` (the integration folder with the bundle)
to it; `hacs.json` has `zip_release` so HACS installs that zip. The release
flow has not run yet.

`sync-issue-labels.yml` is not a check. When a pull request is opened or
reopened (`pull_request_target`, never checks out PR code), it copies the
labels of the issues the PR links to (closing keywords or the Development
sidebar) onto the PR.

`.github/release.yml` configures GitHub's auto-generated release notes. It
groups PRs by label (`breaking-change`, `enhancement`, `bug`,
`documentation`, `dependencies`, everything else last) and skips PRs
labelled `ignore-for-release` and bot authors. The label sync workflow is
what puts the issue labels on PRs.
