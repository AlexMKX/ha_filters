"""Climate Sync integration for TRVZB devices."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import Event, HomeAssistant, ServiceCall, State, callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.util import dt as dt_util

DOMAIN = "climate_sync"
SERVICE_REFRESH = "refresh"
_LOGGER = logging.getLogger(__name__)

# Interval for periodic forced sync
SYNC_INTERVAL = timedelta(minutes=10)


@dataclass
class TRVZBDevice:
    """Represents a TRVZB device with its entities."""

    device_id: str
    device_name: str
    area_id: str
    select_entity_id: str  # select.xxx_temperature_sensor_select
    number_entity_id: str  # number.xxx_external_temperature_input
    last_sync: datetime | None = None


class ClimateSync:
    """Climate Sync coordinator."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the climate sync coordinator."""
        self.hass = hass
        self.devices: dict[str, TRVZBDevice] = {}
        self.area_listeners: dict[str, Any] = {}
        self.timer_unsub: Any = None
        self.setup_done: bool = False

    async def async_setup(self) -> None:
        """Set up climate sync."""
        # Prevent double setup
        if self.setup_done:
            _LOGGER.debug("Setup already done, skipping")
            return
        
        self.setup_done = True
        await self.async_discover_devices()
        await self.async_setup_external_mode()
        await self.async_setup_listeners()
        
        # Setup periodic sync timer
        self.timer_unsub = async_track_time_interval(
            self.hass, self._async_periodic_sync, SYNC_INTERVAL
        )

    async def async_discover_devices(self) -> None:
        """Discover all TRVZB devices in areas with temperature sensors."""
        area_registry = ar.async_get(self.hass)
        device_registry = dr.async_get(self.hass)
        entity_registry = er.async_get(self.hass)

        self.devices.clear()
        discovered_count = 0

        for area in area_registry.async_list_areas():
            # Skip areas without temperature sensor
            if not hasattr(area, 'temperature_entity_id') or not area.temperature_entity_id:
                _LOGGER.debug("Area %s has no temperature_entity_id, skipping", area.name)
                continue

            _LOGGER.debug(
                "Processing area %s with temperature sensor %s",
                area.name,
                area.temperature_entity_id,
            )

            # Find all TRVZB devices in this area
            for device in device_registry.devices.values():
                if device.area_id != area.id:
                    continue

                # Check if device is TRVZB by model_id
                if not hasattr(device, 'model_id') or device.model_id != "TRVZB":
                    continue

                _LOGGER.debug("Found TRVZB device: %s in area %s", device.name, area.name)

                # Find required entities for this device
                select_entity = None
                number_entity = None

                for entity in entity_registry.entities.values():
                    if entity.device_id != device.id:
                        continue

                    # Look for temperature_sensor_select entity
                    if (
                        entity.domain == "select"
                        and "temperature_sensor" in entity.entity_id
                    ):
                        select_entity = entity.entity_id

                    # Look for external_temperature_input entity
                    if (
                        entity.domain == "number"
                        and "external_temperature_input" in entity.entity_id
                    ):
                        number_entity = entity.entity_id

                if not select_entity or not number_entity:
                    _LOGGER.warning(
                        "TRVZB device %s missing required entities (select: %s, number: %s)",
                        device.name,
                        select_entity,
                        number_entity,
                    )
                    continue

                trv_device = TRVZBDevice(
                    device_id=device.id,
                    device_name=device.name or device.id,
                    area_id=area.id,
                    select_entity_id=select_entity,
                    number_entity_id=number_entity,
                )

                self.devices[device.id] = trv_device
                discovered_count += 1

                _LOGGER.info(
                    "Registered TRVZB device %s in area %s (select: %s, number: %s)",
                    device.name,
                    area.name,
                    select_entity,
                    number_entity,
                )

        _LOGGER.info("Discovered %d TRVZB devices", discovered_count)

    async def async_setup_external_mode(self) -> None:
        """Set all TRVZB devices to use external temperature sensor."""
        for device in self.devices.values():
            try:
                current_state = self.hass.states.get(device.select_entity_id)
                if current_state and current_state.state != "external":
                    _LOGGER.info(
                        "Setting %s to external mode (was: %s)",
                        device.device_name,
                        current_state.state,
                    )
                    await self.hass.services.async_call(
                        "select",
                        "select_option",
                        {
                            "entity_id": device.select_entity_id,
                            "option": "external",
                        },
                        blocking=True,
                    )
                else:
                    _LOGGER.debug(
                        "%s already in external mode", device.device_name
                    )
            except Exception as e:
                _LOGGER.error(
                    "Failed to set external mode for %s: %s",
                    device.device_name,
                    e,
                )

    async def async_setup_listeners(self) -> None:
        """Set up state change listeners for area temperature sensors."""
        area_registry = ar.async_get(self.hass)

        # Group devices by area
        area_devices: dict[str, list[TRVZBDevice]] = {}
        for device in self.devices.values():
            area_devices.setdefault(device.area_id, []).append(device)

        # Setup listener for each area's temperature sensor
        for area_id, devices in area_devices.items():
            area = area_registry.async_get_area(area_id)
            if not area or not hasattr(area, 'temperature_entity_id') or not area.temperature_entity_id:
                continue

            temp_sensor_id = area.temperature_entity_id

            @callback
            def _make_listener(area_id: str, devices: list[TRVZBDevice]):
                """Create a listener for specific area."""
                
                async def _async_temp_changed(event: Event) -> None:
                    """Handle temperature sensor state change."""
                    new_state = event.data.get("new_state")
                    if not new_state or new_state.state in ("unknown", "unavailable"):
                        return

                    try:
                        temperature = float(new_state.state)
                        _LOGGER.debug(
                            "Temperature changed in area to %.1f°C, syncing %d devices",
                            temperature,
                            len(devices),
                        )
                        for device in devices:
                            await self._async_sync_device(device, temperature)
                    except (ValueError, TypeError) as e:
                        _LOGGER.warning(
                            "Invalid temperature value %s: %s",
                            new_state.state,
                            e,
                        )

                return _async_temp_changed

            listener = async_track_state_change_event(
                self.hass,
                [temp_sensor_id],
                _make_listener(area_id, devices),
            )

            self.area_listeners[area_id] = listener

            _LOGGER.info(
                "Setup listener for %s covering %d TRVZB devices",
                temp_sensor_id,
                len(devices),
            )

    async def _async_sync_device(
        self, device: TRVZBDevice, temperature: float
    ) -> None:
        """Sync temperature to a single TRVZB device."""
        try:
            # Get current external temperature input value
            current_state = self.hass.states.get(device.number_entity_id)
            if not current_state:
                _LOGGER.warning(
                    "Cannot get state for %s", device.number_entity_id
                )
                return

            # Try to get current temperature, but don't fail if it's unknown
            current_temp = None
            skip_sync = False
            
            try:
                current_temp = float(current_state.state)
                # Only skip update if temperature hasn't changed
                if abs(current_temp - temperature) < 0.05:  # 0.05°C tolerance
                    _LOGGER.debug(
                        "Temperature for %s unchanged (%.1f°C), skipping",
                        device.device_name,
                        temperature,
                    )
                    device.last_sync = dt_util.utcnow()
                    skip_sync = True
            except (ValueError, TypeError):
                # Current temperature is unknown/unavailable - we should sync anyway
                _LOGGER.info(
                    "Current temperature for %s is %s, will sync to %.1f°C",
                    device.device_name,
                    current_state.state,
                    temperature,
                )
            
            if skip_sync:
                return

            if current_temp is not None:
                _LOGGER.info(
                    "Syncing %s: %.1f°C -> %.1f°C",
                    device.device_name,
                    current_temp,
                    temperature,
                )
            else:
                _LOGGER.info(
                    "Syncing %s: unknown -> %.1f°C",
                    device.device_name,
                    temperature,
                )

            await self.hass.services.async_call(
                "number",
                "set_value",
                {
                    "entity_id": device.number_entity_id,
                    "value": temperature,
                },
                blocking=True,
            )

            device.last_sync = datetime.now()

        except Exception as e:
            _LOGGER.error(
                "Failed to sync temperature for %s: %s",
                device.device_name,
                e,
            )

    async def _async_periodic_sync(self, now: datetime) -> None:
        """Periodically sync devices that haven't been updated recently."""
        area_registry = ar.async_get(self.hass)
        
        for device in self.devices.values():
            # Skip if recently synced
            if device.last_sync and (now - device.last_sync) < SYNC_INTERVAL:
                continue

            # Get area temperature sensor
            area = area_registry.async_get_area(device.area_id)
            if not area or not hasattr(area, 'temperature_entity_id') or not area.temperature_entity_id:
                continue

            temp_state = self.hass.states.get(area.temperature_entity_id)
            if not temp_state or temp_state.state in ("unknown", "unavailable"):
                continue

            try:
                temperature = float(temp_state.state)
                _LOGGER.debug(
                    "Periodic sync for %s (last sync: %s)",
                    device.device_name,
                    device.last_sync,
                )
                await self._async_sync_device(device, temperature)
            except (ValueError, TypeError) as e:
                _LOGGER.warning(
                    "Invalid temperature for periodic sync: %s", e
                )

    async def async_refresh(self) -> None:
        """Manually refresh all devices."""
        _LOGGER.info("Manual refresh triggered")
        await self.async_discover_devices()
        await self.async_setup_external_mode()
        
        # Remove old listeners
        for listener in self.area_listeners.values():
            listener()
        self.area_listeners.clear()
        
        # Setup new listeners
        await self.async_setup_listeners()

        # Force sync all devices
        await self._async_periodic_sync(dt_util.utcnow())

    async def async_unload(self) -> None:
        """Unload the integration."""
        # Remove listeners
        for listener in self.area_listeners.values():
            listener()
        self.area_listeners.clear()

        # Remove timer
        if self.timer_unsub:
            self.timer_unsub()
            self.timer_unsub = None


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Climate Sync integration."""
    coordinator = ClimateSync(hass)
    hass.data[DOMAIN] = coordinator

    async def _handle_refresh_service(call: ServiceCall) -> None:
        """Handle refresh service call."""
        await coordinator.async_refresh()

    hass.services.async_register(DOMAIN, SERVICE_REFRESH, _handle_refresh_service)

    async def _run_on_start(_: object) -> None:
        """Run setup on Home Assistant start."""
        await coordinator.async_setup()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _run_on_start)

    # Run shortly after startup in case Home Assistant is already running
    hass.async_create_task(coordinator.async_setup())

    return True


async def async_unload_entry(hass: HomeAssistant, entry) -> bool:
    """Handle unloading the integration."""
    coordinator: ClimateSync = hass.data.get(DOMAIN)
    if coordinator:
        await coordinator.async_unload()
    
    tasks = [
        hass.services.async_remove(domain=DOMAIN, service=SERVICE_REFRESH),
    ]
    await asyncio.gather(*tasks, return_exceptions=True)
    return True

