"""Valve platform for Dimmer Valve integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.valve import ValveEntity, ValveEntityFeature
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN, VALVE_TYPE_NORMALLY_CLOSED, VALVE_TYPE_NORMALLY_OPEN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Dimmer Valve platform."""
    if discovery_info is None:
        return

    entities = []
    for dimmer_entity_id, valve_config in discovery_info.items():
        # Create valve entity_id from dimmer entity_id
        # light.mast_valve_l1 -> valve.mast_valve_l1
        valve_entity_id = dimmer_entity_id.replace("light.", "valve.", 1)

        entity = DimmerValve(
            hass=hass,
            dimmer_entity_id=dimmer_entity_id,
            valve_entity_id=valve_entity_id,
            valve_type=valve_config["type"],
            max_brightness=valve_config["max"],
        )
        entities.append(entity)
        _LOGGER.info(
            "Created valve %s from dimmer %s (type: %s, max: %d)",
            valve_entity_id,
            dimmer_entity_id,
            valve_config["type"],
            valve_config["max"],
        )

    async_add_entities(entities, True)


class DimmerValve(ValveEntity, RestoreEntity):
    """Representation of a Dimmer Valve."""

    _attr_should_poll = False
    _attr_reports_position = True
    _attr_supported_features = (
        ValveEntityFeature.OPEN
        | ValveEntityFeature.CLOSE
        | ValveEntityFeature.SET_POSITION
    )

    def __init__(
        self,
        hass: HomeAssistant,
        dimmer_entity_id: str,
        valve_entity_id: str,
        valve_type: str,
        max_brightness: int = 255,
    ) -> None:
        """Initialize the Dimmer Valve."""
        self.hass = hass
        self._dimmer_entity_id = dimmer_entity_id
        self._valve_type = valve_type
        self._max_brightness = max_brightness
        self._attr_unique_id = f"dimmer_valve_{dimmer_entity_id}"
        self._attr_name = valve_entity_id.replace("valve.", "").replace("_", " ").title()
        self.entity_id = valve_entity_id

        # Internal state
        self._current_position: int | None = None
        self._position_raw: int = 0  # Raw position (0-255)
        self._is_closed: bool | None = None
        self._dimmer_listener = None
        self._updating_from_dimmer = False
        self._updating_from_valve = False

        _LOGGER.debug(
            "Initialized DimmerValve: %s (dimmer: %s, type: %s, max: %d)",
            valve_entity_id,
            dimmer_entity_id,
            valve_type,
            max_brightness,
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()

        # Restore previous state
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in (
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
        ):
            self._is_closed = last_state.state == "closed"
            if last_state.attributes.get("current_position") is not None:
                self._current_position = int(last_state.attributes["current_position"])
            
            # Restore position_raw if available, otherwise calculate from position
            if last_state.attributes.get("position_raw") is not None:
                self._position_raw = int(last_state.attributes["position_raw"])
            elif self._current_position is not None:
                self._position_raw = self._position_to_raw(self._current_position)
            
            _LOGGER.debug(
                "Restored state for %s: closed=%s, position=%s, raw=%s",
                self.entity_id,
                self._is_closed,
                self._current_position,
                self._position_raw,
            )

        # Get initial state from dimmer
        await self._async_update_from_dimmer()

        # Setup listener for dimmer state changes
        @callback
        def _async_dimmer_changed(event: Event) -> None:
            """Handle dimmer state change."""
            new_state = event.data.get("new_state")
            if new_state is None:
                return

            self.hass.async_create_task(self._async_update_from_dimmer())

        self._dimmer_listener = async_track_state_change_event(
            self.hass, [self._dimmer_entity_id], _async_dimmer_changed
        )

        _LOGGER.debug("Setup state listener for dimmer %s", self._dimmer_entity_id)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        if self._dimmer_listener:
            self._dimmer_listener()
            self._dimmer_listener = None

    @property
    def current_valve_position(self) -> int | None:
        """Return current position of the valve (0-100)."""
        return self._current_position

    @property
    def is_closed(self) -> bool | None:
        """Return if the valve is closed."""
        return self._is_closed

    @property
    def is_closing(self) -> bool:
        """Return if the valve is closing."""
        return False

    @property
    def is_opening(self) -> bool:
        """Return if the valve is opening."""
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        return {
            "position_raw": self._position_raw,
            "max_brightness": self._max_brightness,
        }

    def _position_to_raw(self, position: int) -> int:
        """Convert valve position (0-100%) to raw position (0-255)."""
        return round(position * 255 / 100)

    def _raw_to_position(self, raw: int) -> int:
        """Convert raw position (0-255) to valve position (0-100%)."""
        return round(raw * 100 / 255)

    def _raw_to_brightness(self, raw: int) -> int:
        """Convert raw position (0-255) to dimmer brightness (0-max)."""
        # First scale from 0-255 to 0-max
        brightness = round(raw * self._max_brightness / 255)
        
        # Apply valve type transformation
        if self._valve_type == VALVE_TYPE_NORMALLY_OPEN:
            # NO: high raw = low brightness (inverted)
            brightness = self._max_brightness - brightness
        
        return brightness

    def _brightness_to_raw(self, brightness: int) -> int:
        """Convert dimmer brightness (0-max) to raw position (0-255)."""
        # Apply valve type transformation first
        if self._valve_type == VALVE_TYPE_NORMALLY_OPEN:
            # NO: invert brightness
            brightness = self._max_brightness - brightness
        
        # Scale from 0-max to 0-255
        return round(brightness * 255 / self._max_brightness)

    async def _async_update_from_dimmer(self) -> None:
        """Update valve state from dimmer state."""
        if self._updating_from_valve:
            _LOGGER.debug("Skipping update from dimmer (currently updating from valve)")
            return

        self._updating_from_dimmer = True
        try:
            dimmer_state = self.hass.states.get(self._dimmer_entity_id)
            if dimmer_state is None:
                _LOGGER.warning("Dimmer entity %s not found", self._dimmer_entity_id)
                return

            if dimmer_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                _LOGGER.debug("Dimmer %s is unavailable", self._dimmer_entity_id)
                return

            # Get brightness from dimmer
            brightness = dimmer_state.attributes.get("brightness", 0)
            if dimmer_state.state == "off":
                brightness = 0

            # Convert to raw position and then to valve position
            new_raw = self._brightness_to_raw(brightness)
            new_position = self._raw_to_position(new_raw)
            
            old_position = self._current_position
            old_raw = self._position_raw

            if new_position != old_position or new_raw != old_raw:
                self._position_raw = new_raw
                self._current_position = new_position
                self._is_closed = new_position == 0
                self.async_write_ha_state()
                _LOGGER.debug(
                    "Updated %s from dimmer: brightness=%d -> raw=%d -> position=%d%%",
                    self.entity_id,
                    brightness,
                    new_raw,
                    new_position,
                )
        finally:
            self._updating_from_dimmer = False

    async def _async_update_dimmer(self, target_position: int) -> None:
        """Update dimmer brightness from valve position."""
        if self._updating_from_dimmer:
            _LOGGER.debug("Skipping update to dimmer (currently updating from dimmer)")
            return

        self._updating_from_valve = True
        try:
            # Convert position to raw, then to brightness
            raw = self._position_to_raw(target_position)
            brightness = self._raw_to_brightness(raw)

            _LOGGER.debug(
                "Updating dimmer %s: position=%d%% -> raw=%d -> brightness=%d",
                self._dimmer_entity_id,
                target_position,
                raw,
                brightness,
            )

            # Turn on/off or set brightness
            if brightness == 0:
                await self.hass.services.async_call(
                    "light",
                    SERVICE_TURN_OFF,
                    {ATTR_ENTITY_ID: self._dimmer_entity_id},
                    blocking=True,
                )
            else:
                await self.hass.services.async_call(
                    "light",
                    SERVICE_TURN_ON,
                    {
                        ATTR_ENTITY_ID: self._dimmer_entity_id,
                        "brightness": brightness,
                    },
                    blocking=True,
                )

            # Update internal state
            self._position_raw = raw
            self._current_position = target_position
            self._is_closed = target_position == 0
            self.async_write_ha_state()
        finally:
            self._updating_from_valve = False

    async def async_open_valve(self, **kwargs: Any) -> None:
        """Open the valve."""
        _LOGGER.debug("Opening valve %s", self.entity_id)
        await self._async_update_dimmer(100)

    async def async_close_valve(self, **kwargs: Any) -> None:
        """Close the valve."""
        _LOGGER.debug("Closing valve %s", self.entity_id)
        await self._async_update_dimmer(0)

    async def async_set_valve_position(self, position: int, **kwargs: Any) -> None:
        """Set the valve position."""
        _LOGGER.debug("Setting valve %s position to %d%%", self.entity_id, position)
        await self._async_update_dimmer(position)

