"""End-to-end tests for the Auto Area Assign integration."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from types import MappingProxyType
import sys

import pytest

from homeassistant.config_entries import ConfigEntries, ConfigEntry, ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er

sys.path.append(str(Path(__file__).resolve().parents[1]))

from custom_components.auto_area_assign import DOMAIN, SERVICE_REFRESH, async_setup


@asynccontextmanager
async def _hass_environment(tmp_path):
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
        version=1,
        minor_version=1,
        discovery_keys=MappingProxyType({}),
        unique_id=None,
        entry_id="test-entry",
        pref_disable_new_entities=None,
        pref_disable_polling=None,
        disabled_by=None,
        state=ConfigEntryState.NOT_LOADED,
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


def _run_async_test(coro):
    """Helper to execute asynchronous test bodies without pytest-asyncio."""

    return asyncio.run(coro)


def test_assigns_area_via_refresh_service(tmp_path):
    async def _test():
        async with _hass_environment(tmp_path) as (
            hass,
            config_entry,
            area_reg,
            device_reg,
            entity_reg,
        ):
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

    _run_async_test(_test())


def test_does_not_override_existing_area(tmp_path):
    async def _test():
        async with _hass_environment(tmp_path) as (
            hass,
            config_entry,
            area_reg,
            device_reg,
            entity_reg,
        ):
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

    _run_async_test(_test())


def test_assigns_on_homeassistant_started_event(tmp_path):
    async def _test():
        async with _hass_environment(tmp_path) as (
            hass,
            config_entry,
            area_reg,
            device_reg,
            entity_reg,
        ):
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

    _run_async_test(_test())
