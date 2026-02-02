from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any, Callable

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.util import slugify

DOMAIN = "automation_run_switch"
PLATFORMS: list[Platform] = [Platform.SWITCH]
SYNC_INTERVAL = timedelta(minutes=1)
_LOGGER = logging.getLogger(__name__)


class AutomationRunSwitchManager:
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._async_add_entities: Callable[[list[SwitchEntity], bool], None] | None = None
        self._timer_unsub: Callable[[], None] | None = None
        self._state_unsub: Callable[[], None] | None = None
        self._entities_by_automation: dict[str, RunAutomationSwitch] = {}
        self._started: bool = False

    def async_set_platform(self, async_add_entities: Callable[[list[SwitchEntity], bool], None]) -> None:
        self._async_add_entities = async_add_entities

    async def async_start(self) -> None:
        if self._started:
            await self.async_resync()
            return

        self._started = True
        if self._timer_unsub is None:
            self._timer_unsub = async_track_time_interval(
                self.hass, self._async_periodic_resync, SYNC_INTERVAL
            )
        await self.async_resync()

    async def async_unload(self) -> None:
        if self._state_unsub:
            self._state_unsub()
            self._state_unsub = None
        if self._timer_unsub:
            self._timer_unsub()
            self._timer_unsub = None
        for entity in list(self._entities_by_automation.values()):
            await entity.async_remove()
        self._entities_by_automation.clear()

    async def _async_periodic_resync(self, _: datetime) -> None:
        await self.async_resync()

    async def async_resync(self) -> None:
        if self._async_add_entities is None:
            return

        entity_registry = er.async_get(self.hass)
        device_registry = dr.async_get(self.hass)

        automation_entries = [
            entry
            for entry in entity_registry.entities.values()
            if entry.entity_id.startswith("automation.")
        ]
        automation_entity_ids = {entry.entity_id for entry in automation_entries}

        removed = set(self._entities_by_automation) - automation_entity_ids
        for automation_entity_id in removed:
            entity = self._entities_by_automation.pop(automation_entity_id)
            await entity.async_remove()
            if entity.entity_id:
                switch_entry = entity_registry.async_get(entity.entity_id)
                if switch_entry is not None:
                    entity_registry.async_remove(entity.entity_id)

        new_entities: list[RunAutomationSwitch] = []
        for entry in automation_entries:
            entity = self._entities_by_automation.get(entry.entity_id)
            if entity is None:
                entity = RunAutomationSwitch(self.hass, entry)
                self._entities_by_automation[entry.entity_id] = entity
                new_entities.append(entity)
            else:
                entity.async_set_automation_entry(entry)

        if new_entities:
            self._async_add_entities(new_entities, True)
            await self.hass.async_block_till_done()

        if self._state_unsub:
            self._state_unsub()
            self._state_unsub = None

        if automation_entity_ids:
            self._state_unsub = async_track_state_change_event(
                self.hass,
                list(automation_entity_ids),
                self._async_automation_state_changed,
            )

        for automation_entity_id, entity in self._entities_by_automation.items():
            entry = entity.automation_entry
            if entry is None:
                continue
            automation_area_id = entry.area_id
            if automation_area_id is None and entry.device_id:
                device = device_registry.async_get(entry.device_id)
                if device is not None:
                    automation_area_id = device.area_id

            if not entity.entity_id:
                continue

            switch_entry = entity_registry.async_get(entity.entity_id)
            if switch_entry is None:
                continue
            if switch_entry.area_id != automation_area_id:
                entity_registry.async_update_entity(entity.entity_id, area_id=automation_area_id)

    async def _async_automation_state_changed(self, event: Event) -> None:
        automation_entity_id = event.data.get("entity_id")
        entity = self._entities_by_automation.get(automation_entity_id)
        if entity is not None:
            entity.async_write_ha_state()


class RunAutomationSwitch(SwitchEntity):
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, automation_entry: er.RegistryEntry) -> None:
        self._hass = hass
        self._automation_entry: er.RegistryEntry | None = None
        self._automation_entity_id: str = automation_entry.entity_id
        self._automation_key: str = automation_entry.unique_id or automation_entry.entity_id
        self._attr_unique_id = f"{DOMAIN}:{self._automation_key}"
        self._automation_object_id = self._automation_entity_id.split(".", 1)[1]
        self._suggested_object_id = f"ars_{slugify(self._automation_object_id)}"
        self.async_set_automation_entry(automation_entry)

    @property
    def suggested_object_id(self) -> str | None:
        return self._suggested_object_id

    @property
    def automation_entry(self) -> er.RegistryEntry | None:
        return self._automation_entry

    def async_set_automation_entry(self, entry: er.RegistryEntry) -> None:
        self._automation_entry = entry

    @property
    def available(self) -> bool:
        if self._automation_entry is None:
            return False
        return self._automation_entry.disabled_by is None

    @property
    def name(self) -> str | None:
        st = self._hass.states.get(self._automation_entity_id)
        friendly = None
        if st is not None:
            friendly = st.attributes.get("friendly_name")
        return f"run {friendly or self._automation_entity_id}"

    @property
    def is_on(self) -> bool:
        st = self._hass.states.get(self._automation_entity_id)
        if st is None:
            return False
        current = st.attributes.get("current", 0)
        try:
            return int(current) > 0
        except (TypeError, ValueError):
            return False

    @property
    def device_info(self) -> dr.DeviceInfo:
        return dr.DeviceInfo(
            identifiers={(DOMAIN, "automation_run_switch")},
            name="Automation Run Switches",
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._hass.services.async_call(
            "automation",
            "trigger",
            {"entity_id": self._automation_entity_id},
            blocking=True,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._hass.services.async_call(
            "automation",
            "turn_off",
            {"entity_id": self._automation_entity_id, "stop_actions": True},
            blocking=True,
        )
        await self._hass.services.async_call(
            "automation",
            "turn_on",
            {"entity_id": self._automation_entity_id},
            blocking=True,
        )


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    manager = AutomationRunSwitchManager(hass)
    hass.data[DOMAIN] = manager

    async def _run_on_start(_: object) -> None:
        await manager.async_start()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _run_on_start)

    from homeassistant.helpers import discovery

    hass.async_create_task(
        discovery.async_load_platform(hass, Platform.SWITCH, DOMAIN, {}, config)
    )

    hass.async_create_task(manager.async_start())

    return True


async def async_unload_entry(hass: HomeAssistant, entry) -> bool:
    manager: AutomationRunSwitchManager | None = hass.data.get(DOMAIN)
    if manager is not None:
        await manager.async_unload()
    return True
