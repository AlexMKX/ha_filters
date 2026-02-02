"""Unit tests for DimmerValve conversion methods."""
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add custom_components to path
sys.path.insert(0, str(Path(__file__).parent.parent / "custom_components"))

# Import after path adjustment
from dimmer_valve import VALVE_TYPE_NORMALLY_OPEN, VALVE_TYPE_NORMALLY_CLOSED
from dimmer_valve.valve import DimmerValve
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_hass():
    """Create a mock HomeAssistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    return hass


class TestConversionMax255NC:
    """Test conversions with max=255, normally closed."""

    @pytest.fixture
    def valve(self, mock_hass):
        """Create a test valve instance."""
        return DimmerValve(
            hass=mock_hass,
            dimmer_entity_id="light.test",
            valve_entity_id="valve.test",
            valve_type=VALVE_TYPE_NORMALLY_CLOSED,
            max_brightness=255,
        )

    def test_position_to_raw(self, valve):
        """Test position to raw conversion."""
        assert valve._position_to_raw(0) == 0
        assert valve._position_to_raw(50) == 128  # rounded from 127.5
        assert valve._position_to_raw(100) == 255

    def test_raw_to_position(self, valve):
        """Test raw to position conversion."""
        assert valve._raw_to_position(0) == 0
        assert valve._raw_to_position(128) == 50
        assert valve._raw_to_position(255) == 100

    def test_raw_to_brightness_nc(self, valve):
        """Test raw to brightness for normally closed."""
        # NC: no inversion
        assert valve._raw_to_brightness(0) == 0
        assert valve._raw_to_brightness(128) == 128
        assert valve._raw_to_brightness(255) == 255

    def test_brightness_to_raw_nc(self, valve):
        """Test brightness to raw for normally closed."""
        # NC: no inversion
        assert valve._brightness_to_raw(0) == 0
        assert valve._brightness_to_raw(128) == 128
        assert valve._brightness_to_raw(255) == 255

    def test_full_cycle_nc(self, valve):
        """Test full conversion cycle for normally closed."""
        # position -> raw -> brightness -> raw -> position
        test_positions = [0, 25, 50, 75, 100]
        for pos in test_positions:
            raw = valve._position_to_raw(pos)
            brightness = valve._raw_to_brightness(raw)
            raw2 = valve._brightness_to_raw(brightness)
            pos2 = valve._raw_to_position(raw2)
            assert abs(pos - pos2) <= 1, f"Position cycle failed for {pos}: got {pos2}"


class TestConversionMax255NO:
    """Test conversions with max=255, normally open."""

    @pytest.fixture
    def valve(self, mock_hass):
        """Create a test valve instance."""
        return DimmerValve(
            hass=mock_hass,
            dimmer_entity_id="light.test",
            valve_entity_id="valve.test",
            valve_type=VALVE_TYPE_NORMALLY_OPEN,
            max_brightness=255,
        )

    def test_raw_to_brightness_no(self, valve):
        """Test raw to brightness for normally open."""
        # NO: inverted
        assert valve._raw_to_brightness(0) == 255
        assert valve._raw_to_brightness(128) == 127  # 255 - 128
        assert valve._raw_to_brightness(255) == 0

    def test_brightness_to_raw_no(self, valve):
        """Test brightness to raw for normally open."""
        # NO: inverted
        assert valve._brightness_to_raw(255) == 0
        assert valve._brightness_to_raw(128) == 127
        assert valve._brightness_to_raw(0) == 255

    def test_full_cycle_no(self, valve):
        """Test full conversion cycle for normally open."""
        # position -> raw -> brightness -> raw -> position
        test_positions = [0, 25, 50, 75, 100]
        for pos in test_positions:
            raw = valve._position_to_raw(pos)
            brightness = valve._raw_to_brightness(raw)
            raw2 = valve._brightness_to_raw(brightness)
            pos2 = valve._raw_to_position(raw2)
            assert abs(pos - pos2) <= 1, f"Position cycle failed for {pos}: got {pos2}"


class TestConversionMax100NC:
    """Test conversions with max=100, normally closed."""

    @pytest.fixture
    def valve(self, mock_hass):
        """Create a test valve instance."""
        return DimmerValve(
            hass=mock_hass,
            dimmer_entity_id="light.test",
            valve_entity_id="valve.test",
            valve_type=VALVE_TYPE_NORMALLY_CLOSED,
            max_brightness=100,
        )

    def test_raw_to_brightness_max100(self, valve):
        """Test raw to brightness with max=100."""
        # raw=0 -> brightness=0
        assert valve._raw_to_brightness(0) == 0
        # raw=128 (50%) -> brightness=50 (100 * 128 / 255)
        assert valve._raw_to_brightness(128) == 50
        # raw=255 (100%) -> brightness=100
        assert valve._raw_to_brightness(255) == 100

    def test_brightness_to_raw_max100(self, valve):
        """Test brightness to raw with max=100."""
        # brightness=0 -> raw=0
        assert valve._brightness_to_raw(0) == 0
        # brightness=50 -> raw=128 (50 * 255 / 100)
        assert valve._brightness_to_raw(50) == 128
        # brightness=100 -> raw=255
        assert valve._brightness_to_raw(100) == 255

    def test_full_cycle_max100_nc(self, valve):
        """Test full conversion cycle with max=100."""
        test_cases = [
            (0, 0, 0),      # position=0% -> raw=0 -> brightness=0
            (50, 128, 50),  # position=50% -> raw=128 -> brightness=50
            (100, 255, 100),  # position=100% -> raw=255 -> brightness=100
        ]
        for pos, expected_raw, expected_brightness in test_cases:
            raw = valve._position_to_raw(pos)
            assert abs(raw - expected_raw) <= 1, f"Raw mismatch for pos={pos}"
            
            brightness = valve._raw_to_brightness(raw)
            assert abs(brightness - expected_brightness) <= 1, f"Brightness mismatch for pos={pos}"
            
            # Reverse
            raw2 = valve._brightness_to_raw(brightness)
            pos2 = valve._raw_to_position(raw2)
            assert abs(pos - pos2) <= 1, f"Position cycle failed for {pos}: got {pos2}"


class TestConversionMax50NO:
    """Test conversions with max=50, normally open."""

    @pytest.fixture
    def valve(self, mock_hass):
        """Create a test valve instance."""
        return DimmerValve(
            hass=mock_hass,
            dimmer_entity_id="light.test",
            valve_entity_id="valve.test",
            valve_type=VALVE_TYPE_NORMALLY_OPEN,
            max_brightness=50,
        )

    def test_raw_to_brightness_max50_no(self, valve):
        """Test raw to brightness with max=50, NO."""
        # NO: inverted
        # raw=0 -> brightness_before_invert=0 -> brightness=50-0=50
        assert valve._raw_to_brightness(0) == 50
        # raw=128 (50%) -> brightness_before_invert=25 -> brightness=50-25=25
        assert valve._raw_to_brightness(128) == 25
        # raw=255 (100%) -> brightness_before_invert=50 -> brightness=50-50=0
        assert valve._raw_to_brightness(255) == 0

    def test_brightness_to_raw_max50_no(self, valve):
        """Test brightness to raw with max=50, NO."""
        # NO: invert first, then scale
        # brightness=50 -> inverted=0 -> raw=0
        assert valve._brightness_to_raw(50) == 0
        # brightness=25 -> inverted=25 -> raw=128 (25 * 255 / 50)
        assert valve._brightness_to_raw(25) == 128
        # brightness=0 -> inverted=50 -> raw=255
        assert valve._brightness_to_raw(0) == 255

    def test_full_cycle_max50_no(self, valve):
        """Test full conversion cycle with max=50, NO."""
        test_cases = [
            (0, 0, 50),      # position=0% -> raw=0 -> brightness=50
            (50, 128, 25),   # position=50% -> raw=128 -> brightness=25
            (100, 255, 0),   # position=100% -> raw=255 -> brightness=0
        ]
        for pos, expected_raw, expected_brightness in test_cases:
            raw = valve._position_to_raw(pos)
            assert abs(raw - expected_raw) <= 1, f"Raw mismatch for pos={pos}"
            
            brightness = valve._raw_to_brightness(raw)
            assert abs(brightness - expected_brightness) <= 1, f"Brightness mismatch for pos={pos}"
            
            # Reverse
            raw2 = valve._brightness_to_raw(brightness)
            pos2 = valve._raw_to_position(raw2)
            assert abs(pos - pos2) <= 1, f"Position cycle failed for {pos}: got {pos2}"


class TestEdgeCases:
    """Test edge cases and rounding."""

    @pytest.fixture
    def valve_max100(self, mock_hass):
        """Create a test valve with max=100."""
        return DimmerValve(
            hass=mock_hass,
            dimmer_entity_id="light.test",
            valve_entity_id="valve.test",
            valve_type=VALVE_TYPE_NORMALLY_CLOSED,
            max_brightness=100,
        )

    def test_intermediate_values(self, valve_max100):
        """Test intermediate values for proper rounding."""
        # Test various position values
        test_positions = [1, 10, 23, 37, 49, 51, 63, 77, 90, 99]
        for pos in test_positions:
            raw = valve_max100._position_to_raw(pos)
            brightness = valve_max100._raw_to_brightness(raw)
            raw2 = valve_max100._brightness_to_raw(brightness)
            pos2 = valve_max100._raw_to_position(raw2)
            
            # Allow small rounding errors
            assert abs(pos - pos2) <= 2, f"Position {pos} -> {pos2} (error too large)"

    def test_boundary_values(self, valve_max100):
        """Test boundary values."""
        # Test min/max boundaries
        assert valve_max100._position_to_raw(0) == 0
        assert valve_max100._position_to_raw(100) == 255
        assert valve_max100._raw_to_position(0) == 0
        assert valve_max100._raw_to_position(255) == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
