"""Auto Area Assign integration."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Iterable, List, Sequence

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er
from homeassistant.util import slugify

DOMAIN = "auto_area_assign"
SERVICE_REFRESH = "refresh"
LABEL_IGNORE = "auto_area_ignore"
_LOGGER = logging.getLogger(__name__)


@dataclass
class AliasMapping:
    """Represents the relation between an alias slug and an area id."""

    slug: str
    area_id: str


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Auto Area Assign integration."""

    async def _handle_refresh_service(call: ServiceCall) -> None:
        await _async_assign_areas(hass)

    hass.services.async_register(DOMAIN, SERVICE_REFRESH, _handle_refresh_service)

    async def _run_on_start(_: object) -> None:
        await _async_assign_areas(hass)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _run_on_start)

    # Run shortly after startup in case Home Assistant is already running.
    hass.async_create_task(_async_assign_areas(hass))

    return True


async def _async_assign_areas(hass: HomeAssistant) -> None:
    """Assign areas to devices and entities based on entity object_id prefixes."""
    area_registry = ar.async_get(hass)
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    alias_map = _build_alias_map(area_registry.async_list_areas())

    if not alias_map:
        _LOGGER.info("Alias map is empty, nothing to assign")
        return

    device_assignments = 0
    entity_assignments = 0
    skipped_ignored = 0
    skipped_existing_area = 0

    for entity in entity_registry.entities.values():
        # Extract object_id from entity_id (format: domain.object_id)
        object_id = entity.entity_id.split(".", 1)[1] if "." in entity.entity_id else entity.entity_id
        area_id = _match_area_id(alias_map, object_id)
        if not area_id:
            continue

        # Check if entity has auto_area_ignore label
        if LABEL_IGNORE in entity.labels:
            skipped_ignored += 1
            _LOGGER.debug(
                "Entity %s has label %s, skipping", entity.entity_id, LABEL_IGNORE
            )
            continue

        device_id = entity.device_id
        
        if device_id:
            # Entity has a device - assign area to device
            device = device_registry.async_get(device_id)
            if device is None:
                _LOGGER.debug(
                    "Entity %s references unknown device %s", entity.entity_id, device_id
                )
                continue

            # Check if device has auto_area_ignore label
            if LABEL_IGNORE in device.labels:
                skipped_ignored += 1
                _LOGGER.debug(
                    "Device %s has label %s, skipping", device_id, LABEL_IGNORE
                )
                continue

            if device.area_id:
                skipped_existing_area += 1
                _LOGGER.debug(
                    "Device %s already assigned to area %s, skipping",
                    device_id,
                    device.area_id,
                )
                continue

            device_registry.async_update_device(device_id, area_id=area_id)
            device_assignments += 1
            _LOGGER.info(
                "Assigned area %s to device %s via entity %s",
                area_id,
                device_id,
                entity.entity_id,
            )
        else:
            # Entity has no device - assign area to entity itself
            if entity.area_id:
                skipped_existing_area += 1
                _LOGGER.debug(
                    "Entity %s already assigned to area %s, skipping",
                    entity.entity_id,
                    entity.area_id,
                )
                continue

            entity_registry.async_update_entity(entity.entity_id, area_id=area_id)
            entity_assignments += 1
            _LOGGER.info(
                "Assigned area %s to entity %s (no device)",
                area_id,
                entity.entity_id,
            )

    _LOGGER.info(
        "Auto area assignment finished: %s devices updated, %s entities updated, "
        "%s items with existing area, %s items ignored by label",
        device_assignments,
        entity_assignments,
        skipped_existing_area,
        skipped_ignored,
    )


def _build_alias_map(areas: Iterable[ar.AreaEntry]) -> List[AliasMapping]:
    """Build a list of alias mappings sorted by alias length."""
    mappings: List[AliasMapping] = []

    for area in areas:
        alias_candidates = {area.name, *area.aliases}
        for name in alias_candidates:
            slug = slugify(name)
            if not slug:
                continue
            mappings.append(AliasMapping(slug=slug, area_id=area.id))

    mappings.sort(key=lambda item: len(item.slug), reverse=True)
    return mappings


def _match_area_id(alias_map: Sequence[AliasMapping], object_id: str | None) -> str | None:
    """Find an area_id that matches the given object_id."""
    if not object_id:
        return None

    for mapping in alias_map:
        if object_id.startswith(mapping.slug):
            return mapping.area_id
    return None


async def async_unload_entry(hass: HomeAssistant, entry) -> bool:
    """Handle unloading the integration (placeholder for future config entries)."""
    tasks = [
        hass.services.async_remove(domain=DOMAIN, service=SERVICE_REFRESH),
    ]
    await asyncio.gather(*tasks, return_exceptions=True)
    return True

