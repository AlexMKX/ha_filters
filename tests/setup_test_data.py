#!/usr/bin/env python3
"""Script to set up test data for auto_area_assign integration."""
import asyncio
import sys

# Add the HA config dir to Python path to access registries
sys.path.insert(0, '/config')

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er
from homeassistant import config_entries, setup


async def create_test_data():
    """Create test areas, devices, and entities."""
    print("Initializing Home Assistant...")
    hass = HomeAssistant('/config')
    await hass.async_start()
    
    # Get registries
    area_reg = ar.async_get(hass)
    device_reg = dr.async_get(hass)
    entity_reg = er.async_get(hass)
    
    # Create test areas
    print("\n=== Creating test areas ===")
    kitchen = area_reg.async_create("Kitchen")
    kitchen = area_reg.async_update(kitchen.id, aliases=["kitchen", "кухня"])
    print(f"✓ Created area: Kitchen (ID: {kitchen.id}, aliases: {kitchen.aliases})")
    
    living_room = area_reg.async_create("Living Room")
    living_room = area_reg.async_update(living_room.id, aliases=["living_room", "гостиная"])
    print(f"✓ Created area: Living Room (ID: {living_room.id}, aliases: {living_room.aliases})")
    
    bedroom = area_reg.async_create("Bedroom")
    bedroom = area_reg.async_update(bedroom.id, aliases=["bedroom", "спальня"])
    print(f"✓ Created area: Bedroom (ID: {bedroom.id}, aliases: {bedroom.aliases})")
    
    bathroom = area_reg.async_create("Bathroom")
    bathroom = area_reg.async_update(bathroom.id, aliases=["bathroom", "ванная"])
    print(f"✓ Created area: Bathroom (ID: {bathroom.id}, aliases: {bathroom.aliases})")
    
    # Create test devices
    print("\n=== Creating test devices ===")
    
    # Kitchen device (should be auto-assigned)
    kitchen_device = device_reg.async_get_or_create(
        config_entry_id="test_config",
        identifiers={("test", "kitchen_sensor_001")},
        name="Kitchen Multisensor",
        manufacturer="Test Corp",
        model="Sensor Pro",
    )
    print(f"✓ Created device: Kitchen Multisensor (ID: {kitchen_device.id})")
    
    # Living room device (should be auto-assigned)
    living_device = device_reg.async_get_or_create(
        config_entry_id="test_config",
        identifiers={("test", "living_room_sensor_001")},
        name="Living Room Climate",
        manufacturer="Test Corp",
        model="Climate Plus",
    )
    print(f"✓ Created device: Living Room Climate (ID: {living_device.id})")
    
    # Bedroom device (should be auto-assigned)
    bedroom_device = device_reg.async_get_or_create(
        config_entry_id="test_config",
        identifiers={("test", "bedroom_sensor_001")},
        name="Bedroom Sensor",
        manufacturer="Test Corp",
        model="Sensor Lite",
    )
    print(f"✓ Created device: Bedroom Sensor (ID: {bedroom_device.id})")
    
    # Unassigned device (should NOT be auto-assigned - wrong prefix)
    unassigned_device = device_reg.async_get_or_create(
        config_entry_id="test_config",
        identifiers={("test", "random_sensor_001")},
        name="Random Sensor",
        manufacturer="Test Corp",
        model="Sensor X",
    )
    print(f"✓ Created device: Random Sensor (ID: {unassigned_device.id})")
    
    # Create test entities linked to devices
    print("\n=== Creating test entities ===")
    
    # Kitchen entities
    entity_reg.async_get_or_create(
        "sensor",
        "test",
        "kitchen_temp_001",
        suggested_object_id="kitchen_temperature",
        original_name="Kitchen Temperature",
        device_id=kitchen_device.id,
    )
    print(f"✓ Created entity: sensor.kitchen_temperature (device: {kitchen_device.name})")
    
    entity_reg.async_get_or_create(
        "sensor",
        "test",
        "kitchen_humid_001",
        suggested_object_id="kitchen_humidity",
        original_name="Kitchen Humidity",
        device_id=kitchen_device.id,
    )
    print(f"✓ Created entity: sensor.kitchen_humidity (device: {kitchen_device.name})")
    
    # Living room entity
    entity_reg.async_get_or_create(
        "sensor",
        "test",
        "living_room_temp_001",
        suggested_object_id="living_room_temperature",
        original_name="Living Room Temperature",
        device_id=living_device.id,
    )
    print(f"✓ Created entity: sensor.living_room_temperature (device: {living_device.name})")
    
    # Bedroom entity
    entity_reg.async_get_or_create(
        "sensor",
        "test",
        "bedroom_temp_001",
        suggested_object_id="bedroom_temperature",
        original_name="Bedroom Temperature",
        device_id=bedroom_device.id,
    )
    print(f"✓ Created entity: sensor.bedroom_temperature (device: {bedroom_device.name})")
    
    # Unassigned entity (wrong prefix)
    entity_reg.async_get_or_create(
        "sensor",
        "test",
        "random_temp_001",
        suggested_object_id="random_temperature",
        original_name="Random Temperature",
        device_id=unassigned_device.id,
    )
    print(f"✓ Created entity: sensor.random_temperature (device: {unassigned_device.name})")
    
    # Check current device area assignments
    print("\n=== Current device area assignments (before auto_area_assign) ===")
    for device in [kitchen_device, living_device, bedroom_device, unassigned_device]:
        device = device_reg.async_get(device.id)
        print(f"  {device.name}: area_id = {device.area_id}")
    
    print("\n✅ Test data created successfully!")
    print("\nNext steps:")
    print("1. Restart Home Assistant or call the auto_area_assign.refresh service")
    print("2. Check that devices were auto-assigned to areas")
    print("\nTo call the service from inside the container:")
    print("  docker exec ha_test python3 -c 'import asyncio; from homeassistant.core import HomeAssistant; asyncio.run(...)'")
    
    await hass.async_stop()


if __name__ == "__main__":
    asyncio.run(create_test_data())

