from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from types import MappingProxyType
import sys

import pytest

from homeassistant.config_entries import ConfigEntries, ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er
from homeassistant import loader

sys.path.append(str(Path(__file__).resolve().parents[3]))

from custom_components.automation_run_switch import DOMAIN, async_setup


def _run(coro):
    return asyncio.run(coro)


@asynccontextmanager
async def _hass_environment(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    loader.async_setup(hass)
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
        subentries_data=(),
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


def test_creates_switch_entity_and_sets_area(tmp_path):
    async def _test():
        async with _hass_environment(tmp_path) as (
            hass,
            config_entry,
            area_reg,
            device_reg,
            entity_reg,
        ):
            area = area_reg.async_create("Kitchen")

            automation = entity_reg.async_get_or_create(
                "automation",
                "test_platform",
                "unique-automation-1",
                suggested_object_id="my_auto",
                config_entry=config_entry,
            )
            entity_reg.async_update_entity(automation.entity_id, area_id=area.id)

            hass.states.async_set(
                automation.entity_id,
                "on",
                {"current": 0, "friendly_name": "My Automation"},
            )

            assert await async_setup(hass, {})
            await hass.async_block_till_done()

            switch_state = hass.states.get("switch.ars_my_auto")
            assert switch_state is not None
            assert switch_state.state == "off"

            switch_entry = entity_reg.async_get("switch.ars_my_auto")
            assert switch_entry is not None
            assert switch_entry.area_id == area.id

    _run(_test())


def test_switch_tracks_running_state(tmp_path):
    async def _test():
        async with _hass_environment(tmp_path) as (
            hass,
            config_entry,
            area_reg,
            device_reg,
            entity_reg,
        ):
            automation = entity_reg.async_get_or_create(
                "automation",
                "test_platform",
                "unique-automation-1",
                suggested_object_id="my_auto",
                config_entry=config_entry,
            )

            hass.states.async_set(
                automation.entity_id,
                "on",
                {"current": 0, "friendly_name": "My Automation"},
            )

            assert await async_setup(hass, {})
            await hass.async_block_till_done()

            hass.states.async_set(
                automation.entity_id,
                "on",
                {"current": 1, "friendly_name": "My Automation"},
            )
            await hass.async_block_till_done()

            switch_state = hass.states.get("switch.ars_my_auto")
            assert switch_state is not None
            assert switch_state.state == "on"

    _run(_test())


def test_switch_turn_on_triggers_automation(tmp_path):
    async def _test():
        async with _hass_environment(tmp_path) as (
            hass,
            config_entry,
            area_reg,
            device_reg,
            entity_reg,
        ):
            automation = entity_reg.async_get_or_create(
                "automation",
                "test_platform",
                "unique-automation-1",
                suggested_object_id="my_auto",
                config_entry=config_entry,
            )

            hass.states.async_set(
                automation.entity_id,
                "on",
                {"current": 0, "friendly_name": "My Automation"},
            )

            async def _trigger_service(_call):
                hass.states.async_set(
                    automation.entity_id,
                    "on",
                    {"current": 1, "friendly_name": "My Automation"},
                )

            hass.services.async_register("automation", "trigger", _trigger_service)
            hass.services.async_register("automation", "turn_off", lambda _call: None)
            hass.services.async_register("automation", "turn_on", lambda _call: None)

            assert await async_setup(hass, {})
            await hass.async_block_till_done()

            await hass.services.async_call(
                "switch",
                "turn_on",
                {"entity_id": "switch.ars_my_auto"},
                blocking=True,
            )
            await hass.async_block_till_done()

            switch_state = hass.states.get("switch.ars_my_auto")
            assert switch_state is not None
            assert switch_state.state == "on"

    _run(_test())


def test_device_id_persists_across_restart(tmp_path):
    async def _test_once(hass, config_entry, entity_reg):
        automation = entity_reg.async_get_or_create(
            "automation",
            "test_platform",
            "unique-automation-1",
            suggested_object_id="my_auto",
            config_entry=config_entry,
        )
        hass.states.async_set(
            automation.entity_id,
            "on",
            {"current": 0, "friendly_name": "My Automation"},
        )
        assert await async_setup(hass, {})
        await hass.async_block_till_done()
        switch_entry = entity_reg.async_get("switch.ars_my_auto")
        assert switch_entry is not None
        return switch_entry.device_id

    async def _test():
        async with _hass_environment(tmp_path) as (
            hass,
            config_entry,
            area_reg,
            device_reg,
            entity_reg,
        ):
            device_id_1 = await _test_once(hass, config_entry, entity_reg)

        async with _hass_environment(tmp_path) as (
            hass,
            config_entry,
            area_reg,
            device_reg,
            entity_reg,
        ):
            device_id_2 = await _test_once(hass, config_entry, entity_reg)

        assert device_id_1 == device_id_2

    _run(_test())


def test_switch_removed_when_automation_removed(tmp_path):
    async def _test():
        async with _hass_environment(tmp_path) as (
            hass,
            config_entry,
            area_reg,
            device_reg,
            entity_reg,
        ):
            automation = entity_reg.async_get_or_create(
                "automation",
                "test_platform",
                "unique-automation-1",
                suggested_object_id="my_auto",
                config_entry=config_entry,
            )
            hass.states.async_set(
                automation.entity_id,
                "on",
                {"current": 0, "friendly_name": "My Automation"},
            )
            assert await async_setup(hass, {})
            await hass.async_block_till_done()

            entity_reg.async_remove(automation.entity_id)
            await hass.async_block_till_done()

            manager = hass.data[DOMAIN]
            await manager.async_resync()
            await hass.async_block_till_done()

            assert entity_reg.async_get("switch.ars_my_auto") is None

    _run(_test())
