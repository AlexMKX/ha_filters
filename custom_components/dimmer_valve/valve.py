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
    for dimmer_entity_id, valve_type in discovery_info.items():
        # Create valve entity_id from dimmer entity_id
        # light.mast_valve_l1 -> valve.mast_valve_l1
        valve_entity_id = dimmer_entity_id.replace("light.", "valve.", 1)

        entity = DimmerValve(
            hass=hass,
            dimmer_entity_id=dimmer_entity_id,
            valve_entity_id=valve_entity_id,
            valve_type=valve_type,
        )
        entities.append(entity)
        _LOGGER.info(
            "Created valve %s from dimmer %s (type: %s)",
            valve_entity_id,
            dimmer_entity_id,
            valve_type,
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
    ) -> None:
        """Initialize the Dimmer Valve."""
        self.hass = hass
        self._dimmer_entity_id = dimmer_entity_id
        self._valve_type = valve_type
        self._attr_unique_id = f"dimmer_valve_{dimmer_entity_id}"
        self._attr_name = valve_entity_id.replace("valve.", "").replace("_", " ").title()
        self.entity_id = valve_entity_id

        # Internal state
        self._current_position: int | None = None
        self._is_closed: bool | None = None
        self._dimmer_listener = None
        self._updating_from_dimmer = False
        self._updating_from_valve = False

        _LOGGER.debug(
            "Initialized DimmerValve: %s (dimmer: %s, type: %s)",
            valve_entity_id,
            dimmer_entity_id,
            valve_type,
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
            _LOGGER.debug(
                "Restored state for %s: closed=%s, position=%s",
                self.entity_id,
                self._is_closed,
                self._current_position,
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

    def _dimmer_brightness_to_valve_position(self, brightness: int) -> int:
        """Convert dimmer brightness (0-255) to valve position (0-100)."""
        # Convert brightness from 0-255 to 0-100
        brightness_percent = int((brightness / 255) * 100)

        # Apply valve type transformation
        if self._valve_type == VALVE_TYPE_NORMALLY_OPEN:
            # NO: 100% brightness = 0% valve position (closed)
            return 100 - brightness_percent
        else:
            # NC: 100% brightness = 100% valve position (open)
            return brightness_percent

    def _valve_position_to_dimmer_brightness(self, position: int) -> int:
        """Convert valve position (0-100) to dimmer brightness (0-255)."""
        # Apply valve type transformation
        if self._valve_type == VALVE_TYPE_NORMALLY_OPEN:
            # NO: 0% valve position = 100% brightness (closed)
            brightness_percent = 100 - position
        else:
            # NC: 100% valve position = 100% brightness (open)
            brightness_percent = position

        # Convert from 0-100 to 0-255
        return int((brightness_percent / 100) * 255)

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

            # Convert to valve position
            new_position = self._dimmer_brightness_to_valve_position(brightness)
            old_position = self._current_position

            if new_position != old_position:
                self._current_position = new_position
                self._is_closed = new_position == 0
                self.async_write_ha_state()
                _LOGGER.debug(
                    "Updated %s from dimmer: brightness=%d -> position=%d%%",
                    self.entity_id,
                    brightness,
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
            brightness = self._valve_position_to_dimmer_brightness(target_position)

            _LOGGER.debug(
                "Updating dimmer %s: position=%d%% -> brightness=%d",
                self._dimmer_entity_id,
                target_position,
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

