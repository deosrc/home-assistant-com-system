# home-assistant-com-system

Com System is a notification distribution system for Home Assistant, built
as a custom integration. See [PLAN.md](PLAN.md) for the design and
[docs/](docs/README.md) for the documentation.

## Development

Development happens in a devcontainer. Open the repository in VS Code and
choose **Reopen in Container**. The container provides:

- Python 3.14 with Home Assistant 2026.10.4 (the pinned minimum version),
  `pytest-homeassistant-custom-component`, `debugpy` and `ruff`.
- Node.js (LTS) with `markdownlint-cli2`.
- Port 8123 forwarded for the Home Assistant UI.

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

### Test and lint

- **Run tests** task, or `python3 -m pytest tests`.
- **Lint Python**: `ruff check .` and `ruff format --check .`.
- **Lint markdown** task, or `npm run lint:md`. All Markdown must pass the
  default markdownlint rules, including the 80 character line limit.

### Continuous integration

GitHub Actions run Ruff, the tests, markdownlint and hassfest on every pull
request and push to `main`. HACS validation is manual-only until the
repository is public.
