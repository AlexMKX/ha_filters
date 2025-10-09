"""End-to-end tests for the Auto Area Assign integration."""
from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
import sys

import pytest
import pytest_asyncio

from homeassistant.config_entries import ConfigEntries, ConfigEntry, ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er

sys.path.append(str(Path(__file__).resolve().parents[1]))

from custom_components.auto_area_assign import DOMAIN, SERVICE_REFRESH, async_setup


@pytest_asyncio.fixture
async def hass_environment(tmp_path) -> tuple[
    HomeAssistant,
    ConfigEntry,
    ar.AreaRegistry,
    dr.DeviceRegistry,
    er.EntityRegistry,
]:
    """Provision a running Home Assistant core with loaded registries."""

    hass = HomeAssistant(str(tmp_path))
    hass.config_entries = ConfigEntries(hass, {})
    await hass.config_entries.async_initialize()

    config_entry = ConfigEntry(
        domain="test_domain",
        title="Test Entry",
        data={},
        options={},
        source="test",
        entry_id="test-entry",
        version=1,
        minor_version=1,
        discovery_keys=MappingProxyType({}),
        unique_id=None,
        pref_disable_new_entities=None,
        pref_disable_polling=None,
        disabled_by=None,
        state=ConfigEntryState.NOT_LOADED,
        subentries_data=None,
        created_at=None,
        modified_at=None,
    )
    hass.config_entries._entries[config_entry.entry_id] = config_entry

    await hass.async_start()

    area_reg = ar.async_get(hass)
    device_reg = dr.async_get(hass)
    entity_reg = er.async_get(hass)

    await area_reg.async_load()
    await device_reg.async_load()
    await entity_reg.async_load()

    try:
        yield hass, config_entry, area_reg, device_reg, entity_reg
    finally:
        await hass.async_stop()
        await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_assigns_area_via_refresh_service(
    hass_environment: tuple[
        HomeAssistant, ConfigEntry, ar.AreaRegistry, dr.DeviceRegistry, er.EntityRegistry
    ],
):
    hass, config_entry, area_reg, device_reg, entity_reg = hass_environment

    kitchen = area_reg.async_create("Kitchen", aliases={"kitchen", "Kitchen"})
    device = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("auto-area", "device-1")},
    )
    entity_reg.async_get_or_create(
        "light",
        "test_platform",
        "unique-1",
        suggested_object_id="kitchen_ceiling",
        config_entry=config_entry,
        device_id=device.id,
    )

    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    await hass.services.async_call(DOMAIN, SERVICE_REFRESH, {}, blocking=True)
    await hass.async_block_till_done()

    updated_device = device_reg.async_get(device.id)
    assert updated_device.area_id == kitchen.id


@pytest.mark.asyncio
async def test_does_not_override_existing_area(
    hass_environment: tuple[
        HomeAssistant, ConfigEntry, ar.AreaRegistry, dr.DeviceRegistry, er.EntityRegistry
    ],
):
    hass, config_entry, area_reg, device_reg, entity_reg = hass_environment

    area_reg.async_create("Bedroom", aliases={"bedroom"})
    other_area = area_reg.async_create("Garage", aliases={"garage"})

    device = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("auto-area", "device-2")},
    )
    device_reg.async_update_device(device.id, area_id=other_area.id)

    entity_reg.async_get_or_create(
        "switch",
        "test_platform",
        "unique-2",
        suggested_object_id="bedroom_lamp",
        config_entry=config_entry,
        device_id=device.id,
    )

    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    await hass.services.async_call(DOMAIN, SERVICE_REFRESH, {}, blocking=True)
    await hass.async_block_till_done()

    updated_device = device_reg.async_get(device.id)
    assert updated_device.area_id == other_area.id


@pytest.mark.asyncio
async def test_assigns_on_homeassistant_started_event(
    hass_environment: tuple[
        HomeAssistant, ConfigEntry, ar.AreaRegistry, dr.DeviceRegistry, er.EntityRegistry
    ],
):
    hass, config_entry, area_reg, device_reg, entity_reg = hass_environment

    hallway = area_reg.async_create("Hallway", aliases={"hall"})

    device = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("auto-area", "device-3")},
    )
    entity_reg.async_get_or_create(
        "sensor",
        "test_platform",
        "unique-3",
        suggested_object_id="hall_motion",
        config_entry=config_entry,
        device_id=device.id,
    )

    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    # Ensure we start from a clean state after the initial background run.
    device_reg.async_update_device(device.id, area_id=None)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    updated_device = device_reg.async_get(device.id)
    assert updated_device.area_id == hallway.id
