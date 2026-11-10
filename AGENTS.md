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
- Panel (in `frontend/`): `npm run lint`, `npm test`, `npm run build`.
  Hot reload: `scripts/develop-frontend`.

## Architecture as built

- Domain `com_system`. The manifest does not use `single_config_entry`
  because receivers are separate config entries.
- One hub entry (`entry_type: hub`) and one entry per receiver
  (`entry_type: custom_receiver` for custom receivers, `receiver` for
  those created from a discovery; both are in `RECEIVER_ENTRY_TYPES`); see
  `const.py`.
- Receiver entry data: `entry_type`, `receiver_type` (missing means
  `custom`), `name`, optional `source_id`. Options: `people` (`person.*`
  entity ids) and `areas` (area ids). Entries are the only storage.
- `receiver.py`: frozen `Receiver` dataclass built by `Receiver.from_entry`.
- `receiver_type.py`: `ReceiverType` is the extension point (id, name,
  capabilities, `async_deliver`, association hooks, `async_detect`,
  `is_source_available`, `discoverable`). Subclass it and call
  `register_receiver_type()` to add a type; ids are unique.
  `CustomReceiverType` is the generic type. `async_deliver` is not wired up
  yet.
- `builtin_types.py`: the six built-in types (mobile app, Alexa Media
  Player, persistent notification, Pushover, webOS TV, Music Assistant),
  registered in `async_setup`. They have detection only; delivery is added
  by each type's own feature. `DeviceReceiverType` offers one receiver per
  device of `source_domain` (source id is the device identifier in that
  domain, and the receiver's entities attach to that device via
  `source_device_identifiers`); `EntryReceiverType` offers one per config
  entry (source id is its unique id, else its entry id; no source device, so
  entities get their own). To add a built-in type, subclass one, set
  `type_id`, `name`, `source_domain`, and add it to `BUILTIN_RECEIVER_TYPES`.
  The Alexa Media Player and Music Assistant device identifiers are assumed
  to be `(domain, <serial or player id>)` and were not checked against the
  integrations.
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
  (`switch.py`, `RestoreEntity`, on by default, the source of truth for
  enabled) and the read-only `notification_receiver` entity
  (`notification_receiver.py`, subclasses `EventEntity`; event types
  `delivered`, `failed`, `skipped`). Both derive from `ReceiverEntity`
  (`entity.py`), which builds the device (`(com_system, entry_id)`), or
  attaches to the source device returned by
  `ReceiverType.source_device_identifiers`, and registers the entity in
  `hass.data[DOMAIN]["entities"][entry_id][entity_key]`
  (`enabled`, `receiver`). Delivery records an attempt with
  `NotificationReceiverEntity.async_record_attempt(result, notification,
  warnings)`; the attributes are `title`, `message`, `priority`, `image`,
  `data`, `warnings` plus static `receiver_type`, `people` and `areas`.
- The `notification_receiver` domain is provided by this integration:
  `async_setup` creates an `EntityComponent` in
  `hass.data[DOMAIN]["notification_receiver_component"]` and the entry calls
  `component.async_setup_entry(entry)` itself. Do not forward the entry to
  `notification_receiver` with `async_forward_entry_setups` (it is not an
  integration, so that fails silently). Home Assistant logs one harmless
  translation warning for the domain. Editing a receiver reloads only that
  entry.
- `config_flow.py`: the user step creates the hub if none exists, otherwise
  it continues to `custom_receiver` (name only). One hub is enforced there.
  The options flow of a receiver edits its people and areas; the hub's
  options flow is a stub. `integration_discovery` aborts with
  `not_available` without a hub or a known type, otherwise sets the unique
  id, aborts if configured and shows a confirm-only `confirm` step that
  creates the receiver (core's Ignore needs no code). Reconfigure is a stub.
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
- `websocket_api.py`: the commands behind the panel
  (`com_system/ping`, `dashboard`, `receivers/list`, `receivers/set_enabled`,
  `discoveries/list`). Every command must have `@websocket_api.require_admin`;
  `tests/test_panel.py` checks all of them reject a read-only user. They read
  the registry and config entries; enabling or disabling calls the receiver's
  switch service, so the switch stays the source of truth. Pending
  discoveries are the `integration_discovery` flows in progress. Add new
  commands to `async_register_commands` and to `COMMANDS` in the test.
- `frontend/`: the panel source (Lit 3, TypeScript, Vite 6, Vitest, ESLint).
  `com-system-panel.ts` is the shell and navigation (routes `dashboard` and
  `receivers` under `/com-system/`), `api.ts` wraps the websocket commands
  (`ComSystemApi`), and each view is its own element (`dashboard-view.ts`,
  `receivers-view.ts`) that refetches when switch states change. Add views
  by adding an element, an entry in `VIEWS` and a command. Elements use
  `static properties` and `declare` fields (no decorators). The build is one
  ES module and the HMR client is imported only when the mode is
  `development`. Commands: `npm run lint`, `npm test`, `npm run build` in
  `frontend/`; `scripts/develop-frontend` for hot reload.
- Strings live in `strings.json`; `translations/en.json` is a copy and must
  be kept in step.
- `hacs.json` records the minimum Home Assistant version; keep it in step
  with `requirements-dev.txt`.

## CI

GitHub Actions workflows in `.github/workflows/` run on pull requests and
pushes to `main`: `lint.yml` (Ruff check and format), `tests.yml` (pytest on
Python 3.14), `frontend.yml` (panel lint, test and build),
`markdownlint.yml`, `hassfest.yml` and `hacs.yml` (HACS
validation). Hassfest also runs nightly. All must pass.

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

HACS validation is temporarily manual-only (`workflow_dispatch`) because the
HACS action fails on a private repository. Restore its triggers when the
repository is made public.
