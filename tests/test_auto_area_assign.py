from pathlib import Path
import asyncio

import sys
import types
from dataclasses import dataclass

import pytest

# Ensure project root on sys.path
sys.path.append(str(Path(__file__).resolve().parents[1]))

# --- Minimal Home Assistant stubs -------------------------------------------------

homeassistant = types.ModuleType("homeassistant")
core = types.ModuleType("homeassistant.core")
const = types.ModuleType("homeassistant.const")
helpers = types.ModuleType("homeassistant.helpers")
area_registry = types.ModuleType("homeassistant.helpers.area_registry")
device_registry = types.ModuleType("homeassistant.helpers.device_registry")
entity_registry = types.ModuleType("homeassistant.helpers.entity_registry")
util = types.ModuleType("homeassistant.util")


class HomeAssistant:
    pass


def slugify(value: str) -> str:
    return value.lower().replace(" ", "_")


core.HomeAssistant = HomeAssistant
core.ServiceCall = object
const.EVENT_HOMEASSISTANT_STARTED = "homeassistant_started"
util.slugify = slugify
helpers.area_registry = area_registry
helpers.device_registry = device_registry
helpers.entity_registry = entity_registry
homeassistant.core = core
homeassistant.const = const
homeassistant.helpers = helpers
homeassistant.util = util

area_registry.async_get = lambda hass: None
device_registry.async_get = lambda hass: None
entity_registry.async_get = lambda hass: None

sys.modules.setdefault("homeassistant", homeassistant)
sys.modules.setdefault("homeassistant.core", core)
sys.modules.setdefault("homeassistant.const", const)
sys.modules.setdefault("homeassistant.helpers", helpers)
sys.modules.setdefault("homeassistant.helpers.area_registry", area_registry)
sys.modules.setdefault("homeassistant.helpers.device_registry", device_registry)
sys.modules.setdefault("homeassistant.helpers.entity_registry", entity_registry)
sys.modules.setdefault("homeassistant.util", util)


from custom_components.auto_area_assign import _async_assign_areas  # noqa: E402


@dataclass
class AreaEntry:
    id: str
    name: str
    aliases: tuple[str, ...] = ()


@dataclass
class DeviceEntry:
    id: str
    area_id: str | None = None


@dataclass
class EntityEntry:
    entity_id: str
    object_id: str
    device_id: str | None


class AreaRegistryStub:
    def __init__(self, areas):
        self._areas = areas

    def async_list_areas(self):
        return self._areas


class DeviceRegistryStub:
    def __init__(self, devices):
        self.devices = {device.id: device for device in devices}
        self.updated: list[tuple[str, str]] = []

    def async_get(self, device_id: str):
        return self.devices.get(device_id)

    def async_update_device(self, device_id: str, *, area_id: str):
        device = self.devices[device_id]
        device.area_id = area_id
        self.updated.append((device_id, area_id))


class EntityRegistryStub:
    def __init__(self, entities):
        self.entities = {entity.entity_id: entity for entity in entities}


class HassStub(HomeAssistant):
    pass


def run_assignment(hass, area_reg, device_reg, entity_reg, monkeypatch):
    monkeypatch.setattr(area_registry, "async_get", lambda hass: area_reg)
    monkeypatch.setattr(device_registry, "async_get", lambda hass: device_reg)
    monkeypatch.setattr(entity_registry, "async_get", lambda hass: entity_reg)
    asyncio.run(_async_assign_areas(hass))


def test_assigns_area_when_device_missing_area(monkeypatch):
    hass = HassStub()
    area = AreaEntry(id="area-1", name="Kitchen", aliases=("kitchen",))
    entity = EntityEntry(
        entity_id="light.kitchen_ceiling",
        object_id="kitchen_ceiling",
        device_id="device-1",
    )
    device = DeviceEntry(id="device-1", area_id=None)

    area_reg = AreaRegistryStub([area])
    device_reg = DeviceRegistryStub([device])
    entity_reg = EntityRegistryStub([entity])

    run_assignment(hass, area_reg, device_reg, entity_reg, monkeypatch)

    assert device.area_id == "area-1"
    assert device_reg.updated == [("device-1", "area-1")]


def test_does_not_override_existing_area(monkeypatch):
    hass = HassStub()
    area = AreaEntry(id="area-1", name="Bedroom", aliases=("bedroom",))
    entity = EntityEntry(
        entity_id="light.bedroom_lamp",
        object_id="bedroom_lamp",
        device_id="device-1",
    )
    device = DeviceEntry(id="device-1", area_id="area-existing")

    area_reg = AreaRegistryStub([area])
    device_reg = DeviceRegistryStub([device])
    entity_reg = EntityRegistryStub([entity])

    run_assignment(hass, area_reg, device_reg, entity_reg, monkeypatch)

    assert device.area_id == "area-existing"
    assert device_reg.updated == []


def test_skips_entities_without_device(monkeypatch):
    hass = HassStub()
    area = AreaEntry(id="area-1", name="Hall", aliases=("hall",))
    entity = EntityEntry(
        entity_id="light.hall_spot",
        object_id="hall_spot",
        device_id=None,
    )

    area_reg = AreaRegistryStub([area])
    device_reg = DeviceRegistryStub([])
    entity_reg = EntityRegistryStub([entity])

    run_assignment(hass, area_reg, device_reg, entity_reg, monkeypatch)

    assert device_reg.updated == []

