# home-assistant-com-system

Com System is a notification distribution system for Home Assistant, built
as a custom integration. See [PLAN.md](PLAN.md) for the design and
[docs/](docs/README.md) for the documentation.

## Development

Development happens in a devcontainer. Open the repository in VS Code and
choose **Reopen in Container**. The container provides:

- Python 3.14 with Home Assistant 2026.10.4 (the pinned minimum version),
  `pytest-homeassistant-custom-component`, `debugpy` and `ruff`.
- Node.js (LTS) with `markdownlint-cli2` and the panel's build tools.
- Ports 8123 (Home Assistant UI) and 5173 (panel dev server) forwarded.

`scripts/setup` runs after the container is created. It installs the
dependencies and links `custom_components/com_system` into the dev config
directory `config/`.

### Start Home Assistant

Run the **Start Home Assistant** task (Terminal > Run Task), or run
`scripts/develop`. Open <http://localhost:8123> and complete onboarding the
first time. Runtime state under `config/` is not committed; only
`config/configuration.yaml` is.

### Debug

The dev configuration enables the Home Assistant `debugpy` integration on
port 5678 without waiting for a debugger. With Home Assistant running, start
the **Home Assistant: attach** launch configuration. Its path mappings map
`custom_components/` in the workspace to the container, so breakpoints set
in the integration work.

### Developing the panel

The panel source is in `frontend/` (Lit and TypeScript, built with Vite).
`scripts/setup` installs its dependencies and builds it once. The build
writes `custom_components/com_system/frontend/dist/`, which is not
committed.

- Rebuild with `npm run build` in `frontend/`.
- Hot reload is on by default: `scripts/develop` (the **Start Home Assistant**
  task) also starts the Vite dev server and sets `COM_SYSTEM_PANEL_DEV_URL`,
  so Home Assistant loads the panel from it. Edit files in `frontend/src` and
  the page reloads. Set `COM_SYSTEM_PANEL_BUNDLE=1` to serve the built bundle
  instead.
- `scripts/develop-frontend` does the same against a throwaway configuration
  with a test admin (`test` / `test-pass-123`) and some checks.

### Testing with the mobile app

`scripts/android-emulator` starts an Android emulator with the Home Assistant
companion app, for testing mobile app receivers. Run it on the host, not in
the devcontainer. It needs the Android SDK with the API 34 Google APIs
x86_64 system image, KVM and the GitHub CLI; the first run creates the
virtual device and downloads the app. In the app, connect to
`http://10.0.2.2:8123`, which is the host's loopback where the devcontainer
forwards Home Assistant. Log in as your dev user, then add the device when Com
System offers it.

### Test and lint

- **Run tests** task, or `python3 -m pytest tests`.
- **Lint Python**: `ruff check .` and `ruff format --check .`.
- **Panel**: in `frontend/`, `npm run lint`, `npm test` and
  `npm run build` (which also type checks).
- **Lint markdown** task, or `npm run lint:md`. All Markdown must pass the
  default markdownlint rules, including the 80 character line limit.

### Continuous integration

GitHub Actions run Ruff, the tests, the panel's lint, test and build,
markdownlint and hassfest on every pull
request and push to `main`. HACS validation is manual-only until the
repository is public.
