"""Admin-only sidebar panel."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PANEL_URL = "com-system"
PANEL_ELEMENT = "com-system-panel"
STATIC_URL = f"/{DOMAIN}_static"
DIST = Path(__file__).parent / "frontend" / "dist"
# Set to the Vite dev server (e.g. http://localhost:5173/src/com-system-panel.ts)
# to load the panel with hot reload instead of the built bundle.
DEV_URL_ENV = "COM_SYSTEM_PANEL_DEV_URL"


async def async_register_panel(hass: HomeAssistant) -> None:
    """Register the static bundle path and the panel."""
    dev_url = os.environ.get(DEV_URL_ENV)
    if dev_url:
        module_url = dev_url
    else:
        if DIST.is_dir():
            await hass.http.async_register_static_paths(
                [StaticPathConfig(STATIC_URL, str(DIST), cache_headers=False)]
            )
        else:
            # Running from source without a build (also the case in the
            # Python tests). The panel is registered but will not load.
            _LOGGER.warning(
                "The panel bundle is missing at %s; run `npm run build` in frontend/",
                DIST,
            )
        module_url = f"{STATIC_URL}/com-system-panel.js"

    await panel_custom.async_register_panel(
        hass,
        webcomponent_name=PANEL_ELEMENT,
        frontend_url_path=PANEL_URL,
        sidebar_title="Com System",
        sidebar_icon="mdi:bullhorn",
        module_url=module_url,
        require_admin=True,
    )


def async_remove_panel(hass: HomeAssistant) -> None:
    """Remove the panel."""
    frontend.async_remove_panel(hass, PANEL_URL)
