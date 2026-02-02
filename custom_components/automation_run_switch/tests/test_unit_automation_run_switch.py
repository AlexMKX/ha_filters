from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

import custom_components.automation_run_switch as ars


def _run(coro):
    return asyncio.run(coro)


@dataclass
class RegistryEntryStub:
    entity_id: str
    unique_id: str | None = None
    area_id: str | None = None
    device_id: str | None = None
    disabled_by: str | None = None


@dataclass
class DeviceEntryStub:
    id: str
    area_id: str | None = None


class EntityRegistryStub:
    def __init__(self, entries: list[RegistryEntryStub]):
        self.entities: dict[str, RegistryEntryStub] = {e.entity_id: e for e in entries}
        self.updated: list[tuple[str, str | None]] = []
        self.removed: list[str] = []

    def async_get(self, entity_id: str):
        return self.entities.get(entity_id)

    def async_update_entity(self, entity_id: str, *, area_id=None, **kwargs):
        entry = self.entities[entity_id]
        entry.area_id = area_id
        self.updated.append((entity_id, area_id))
        return entry

    def async_remove(self, entity_id: str):
        self.entities.pop(entity_id, None)
        self.removed.append(entity_id)


class DeviceRegistryStub:
    def __init__(self, devices: list[DeviceEntryStub]):
        self._devices = {d.id: d for d in devices}

    def async_get(self, device_id: str):
        return self._devices.get(device_id)


class StatesStub:
    def __init__(self, mapping):
        self._mapping = mapping

    def get(self, entity_id: str):
        return self._mapping.get(entity_id)


class ServicesStub:
    def __init__(self):
        self.calls: list[tuple[str, str, dict]] = []

    async def async_call(self, domain: str, service: str, service_data: dict, blocking: bool = False):
        self.calls.append((domain, service, service_data))


class HassStub:
    def __init__(self, states: dict):
        self.states = StatesStub(states)
        self.services = ServicesStub()
        self.data = {}

    async def async_block_till_done(self):
        return


def test_entity_suggested_object_id():
    hass = HassStub({})
    entry = RegistryEntryStub(entity_id="automation.my_test")
    entity = ars.RunAutomationSwitch(hass, entry)  # type: ignore[arg-type]
    assert entity.suggested_object_id == "ars_my_test"


def test_is_on_reflects_current_attribute():
    hass = HassStub(
        {
            "automation.my_test": SimpleNamespace(attributes={"current": 1, "friendly_name": "X"})
        }
    )
    entry = RegistryEntryStub(entity_id="automation.my_test")
    entity = ars.RunAutomationSwitch(hass, entry)  # type: ignore[arg-type]
    assert entity.is_on is True


def test_turn_on_calls_automation_trigger():
    async def _test():
        hass = HassStub({"automation.my_test": SimpleNamespace(attributes={"current": 0})})
        entry = RegistryEntryStub(entity_id="automation.my_test")
        entity = ars.RunAutomationSwitch(hass, entry)  # type: ignore[arg-type]
        await entity.async_turn_on()
        assert hass.services.calls == [
            ("automation", "trigger", {"entity_id": "automation.my_test"})
        ]

    _run(_test())


def test_turn_off_stops_actions_then_turns_on():
    async def _test():
        hass = HassStub({"automation.my_test": SimpleNamespace(attributes={"current": 0})})
        entry = RegistryEntryStub(entity_id="automation.my_test")
        entity = ars.RunAutomationSwitch(hass, entry)  # type: ignore[arg-type]
        await entity.async_turn_off()
        assert hass.services.calls == [
            (
                "automation",
                "turn_off",
                {"entity_id": "automation.my_test", "stop_actions": True},
            ),
            ("automation", "turn_on", {"entity_id": "automation.my_test"}),
        ]

    _run(_test())


def test_disabled_automation_makes_switch_unavailable():
    hass = HassStub({})
    entry = RegistryEntryStub(entity_id="automation.my_test", disabled_by="user")
    entity = ars.RunAutomationSwitch(hass, entry)  # type: ignore[arg-type]
    assert entity.available is False


def test_manager_syncs_switch_area_to_automation_area(monkeypatch):
    async def _test():
        hass = HassStub({})
        automation_entry = RegistryEntryStub(entity_id="automation.my_test", area_id="area-1")
        entity_registry = EntityRegistryStub([automation_entry])
        device_registry = DeviceRegistryStub([])

        monkeypatch.setattr(ars.er, "async_get", lambda _hass: entity_registry)
        monkeypatch.setattr(ars.dr, "async_get", lambda _hass: device_registry)
        monkeypatch.setattr(ars, "async_track_state_change_event", lambda *args, **kwargs: (lambda: None))

        added: list[ars.RunAutomationSwitch] = []

        def _async_add_entities(entities, update_before_add=False):
            for ent in entities:
                ent.entity_id = f"switch.{ent.suggested_object_id}"
                entity_registry.entities[ent.entity_id] = RegistryEntryStub(
                    entity_id=ent.entity_id,
                    unique_id=ent.unique_id,
                    area_id=None,
                    disabled_by=None,
                )
                added.append(ent)

        manager = ars.AutomationRunSwitchManager(hass)
        manager.async_set_platform(_async_add_entities)

        await manager.async_resync()

        assert len(added) == 1
        assert entity_registry.updated == [("switch.ars_my_test", "area-1")]

    _run(_test())
