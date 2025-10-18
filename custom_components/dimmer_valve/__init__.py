"""Dimmer Valve integration for Home Assistant."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

DOMAIN = "dimmer_valve"
SERVICE_REFRESH = "refresh"
PLATFORMS = [Platform.VALVE]

_LOGGER = logging.getLogger(__name__)

# Valve types
VALVE_TYPE_NORMALLY_OPEN = "normally_open"
VALVE_TYPE_NORMALLY_CLOSED = "normally_closed"

VALVE_TYPES = [VALVE_TYPE_NORMALLY_OPEN, VALVE_TYPE_NORMALLY_CLOSED]

# Configuration schema
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                cv.entity_id: vol.In(VALVE_TYPES),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Dimmer Valve integration."""
    domain_config = config.get(DOMAIN, {})

    # Validate configuration
    if not domain_config:
        _LOGGER.info("No dimmer_valve configuration found")
        hass.data[DOMAIN] = {}
        return True

    # Validate that all entity_ids are lights
    for entity_id, valve_type in domain_config.items():
        if not entity_id.startswith("light."):
            _LOGGER.error(
                "Invalid entity_id '%s': only 'light' domain is allowed", entity_id
            )
            return False

    # Store configuration
    hass.data[DOMAIN] = {
        "config": domain_config,
        "valves": {},
    }

    _LOGGER.info(
        "Dimmer Valve configuration loaded with %d dimmers", len(domain_config)
    )

    # Load valve platform using async_forward_entry_setup
    from homeassistant.helpers import discovery
    hass.async_create_task(
        discovery.async_load_platform(
            hass, Platform.VALVE, DOMAIN, domain_config, config
        )
    )

    async def handle_refresh(call: ServiceCall) -> None:
        """Handle refresh service call."""
        _LOGGER.info("Refresh service called")
        # Reload the platform
        await hass.config_entries.async_reload(DOMAIN)

    # Register service
    hass.services.async_register(DOMAIN, SERVICE_REFRESH, handle_refresh)

    # Hide source light entities after a delay to ensure they are created
    async def _hide_lights_delayed():
        await asyncio.sleep(5)
        await _async_hide_light_entities(hass, domain_config.keys())

    hass.async_create_task(_hide_lights_delayed())

    return True


async def _async_hide_light_entities(
    hass: HomeAssistant, entity_ids: list[str]
) -> None:
    """Hide the source light entities."""
    entity_registry = er.async_get(hass)

    for entity_id in entity_ids:
        entity_entry = entity_registry.async_get(entity_id)
        if entity_entry is None:
            _LOGGER.warning("Light entity %s not found in registry", entity_id)
            continue

        # Skip if already hidden
        if entity_entry.hidden_by is not None:
            _LOGGER.debug("Entity %s is already hidden", entity_id)
            continue

        # Hide the entity
        entity_registry.async_update_entity(
            entity_id, hidden_by=er.RegistryEntryHider.INTEGRATION
        )
        _LOGGER.info("Hidden light entity %s", entity_id)


async def async_unload_entry(hass: HomeAssistant, entry) -> bool:
    """Handle unloading the integration."""
    tasks = [
        hass.services.async_remove(domain=DOMAIN, service=SERVICE_REFRESH),
    ]
    await asyncio.gather(*tasks, return_exceptions=True)
    return True

