#!/usr/bin/env python3
"""Script to populate HA registries with test data."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def generate_id():
    """Generate a simple ID."""
    import random
    import string
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=26))


def get_timestamp():
    """Get current timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def create_area_registry(storage_path):
    """Create area registry with test areas."""
    areas_data = {
        "version": 1,
        "minor_version": 2,
        "key": "core.area_registry",
        "data": {
            "areas": [
                {
                    "aliases": ["kitchen", "кухня"],
                    "created_at": get_timestamp(),
                    "floor_id": None,
                    "icon": None,
                    "id": generate_id(),
                    "labels": [],
                    "modified_at": get_timestamp(),
                    "name": "Kitchen",
                    "picture": None
                },
                {
                    "aliases": ["living_room", "гостиная"],
                    "created_at": get_timestamp(),
                    "floor_id": None,
                    "icon": None,
                    "id": generate_id(),
                    "labels": [],
                    "modified_at": get_timestamp(),
                    "name": "Living Room",
                    "picture": None
                },
                {
                    "aliases": ["bedroom", "спальня"],
                    "created_at": get_timestamp(),
                    "floor_id": None,
                    "icon": None,
                    "id": generate_id(),
                    "labels": [],
                    "modified_at": get_timestamp(),
                    "name": "Bedroom",
                    "picture": None
                },
                {
                    "aliases": ["bathroom", "ванная"],
                    "created_at": get_timestamp(),
                    "floor_id": None,
                    "icon": None,
                    "id": generate_id(),
                    "labels": [],
                    "modified_at": get_timestamp(),
                    "name": "Bathroom",
                    "picture": None
                }
            ]
        }
    }
    
    area_file = storage_path / "core.area_registry"
    with open(area_file, 'w') as f:
        json.dump(areas_data, f, indent=2)
    print(f"✓ Created area registry with {len(areas_data['data']['areas'])} areas")
    return areas_data['data']['areas']


def update_device_registry(storage_path):
    """Update device registry with test devices."""
    device_file = storage_path / "core.device_registry"
    
    # Read existing registry
    with open(device_file, 'r') as f:
        registry = json.load(f)
    
    # Create test devices
    test_devices = [
        {
            "area_id": None,
            "config_entries": ["test_integration"],
            "config_entries_subentries": {"test_integration": [None]},
            "configuration_url": None,
            "connections": [],
            "created_at": get_timestamp(),
            "disabled_by": None,
            "entry_type": None,
            "hw_version": None,
            "id": generate_id(),
            "identifiers": [["test", "kitchen_device_001"]],
            "labels": [],
            "manufacturer": "Test Corp",
            "model": "Kitchen Sensor Pro",
            "model_id": None,
            "modified_at": get_timestamp(),
            "name_by_user": None,
            "name": "Kitchen Multisensor",
            "primary_config_entry": "test_integration",
            "serial_number": "KS001",
            "sw_version": "1.0",
            "via_device_id": None
        },
        {
            "area_id": None,
            "config_entries": ["test_integration"],
            "config_entries_subentries": {"test_integration": [None]},
            "configuration_url": None,
            "connections": [],
            "created_at": get_timestamp(),
            "disabled_by": None,
            "entry_type": None,
            "hw_version": None,
            "id": generate_id(),
            "identifiers": [["test", "living_room_device_001"]],
            "labels": [],
            "manufacturer": "Test Corp",
            "model": "Living Room Climate",
            "model_id": None,
            "modified_at": get_timestamp(),
            "name_by_user": None,
            "name": "Living Room Climate Sensor",
            "primary_config_entry": "test_integration",
            "serial_number": "LR001",
            "sw_version": "1.0",
            "via_device_id": None
        },
        {
            "area_id": None,
            "config_entries": ["test_integration"],
            "config_entries_subentries": {"test_integration": [None]},
            "configuration_url": None,
            "connections": [],
            "created_at": get_timestamp(),
            "disabled_by": None,
            "entry_type": None,
            "hw_version": None,
            "id": generate_id(),
            "identifiers": [["test", "bedroom_device_001"]],
            "labels": [],
            "manufacturer": "Test Corp",
            "model": "Bedroom Sensor",
            "model_id": None,
            "modified_at": get_timestamp(),
            "name_by_user": None,
            "name": "Bedroom Temperature Sensor",
            "primary_config_entry": "test_integration",
            "serial_number": "BR001",
            "sw_version": "1.0",
            "via_device_id": None
        },
        {
            "area_id": None,
            "config_entries": ["test_integration"],
            "config_entries_subentries": {"test_integration": [None]},
            "configuration_url": None,
            "connections": [],
            "created_at": get_timestamp(),
            "disabled_by": None,
            "entry_type": None,
            "hw_version": None,
            "id": generate_id(),
            "identifiers": [["test", "random_device_001"]],
            "labels": [],
            "manufacturer": "Test Corp",
            "model": "Random Sensor X",
            "model_id": None,
            "modified_at": get_timestamp(),
            "name_by_user": None,
            "name": "Unassigned Random Sensor",
            "primary_config_entry": "test_integration",
            "serial_number": "RND001",
            "sw_version": "1.0",
            "via_device_id": None
        }
    ]
    
    # Add test devices
    registry['data']['devices'].extend(test_devices)
    
    # Write back
    with open(device_file, 'w') as f:
        json.dump(registry, f, indent=2)
    
    print(f"✓ Added {len(test_devices)} test devices to device registry")
    return test_devices


def update_entity_registry(storage_path, devices):
    """Update entity registry with test entities."""
    entity_file = storage_path / "core.entity_registry"
    
    # Read existing registry
    with open(entity_file, 'r') as f:
        registry = json.load(f)
    
    # Helper to create entity dict
    def make_entity(device_id, entity_id, name, device_class=None, unit=None):
        return {
            "aliases": [],
            "area_id": None,
            "categories": {},
            "capabilities": None,
            "config_entry_id": "test_integration",
            "config_subentry_id": None,
            "created_at": get_timestamp(),
            "device_class": None,
            "device_id": device_id,
            "disabled_by": None,
            "entity_category": None,
            "entity_id": entity_id,
            "has_entity_name": False,
            "hidden_by": None,
            "icon": None,
            "id": generate_id(),
            "labels": [],
            "modified_at": get_timestamp(),
            "name": None,
            "options": {},
            "original_device_class": device_class,
            "original_icon": None,
            "original_name": name,
            "platform": "test",
            "suggested_object_id": None,
            "supported_features": 0,
            "translation_key": None,
            "unique_id": f"test_{entity_id.split('.')[-1]}",
            "previous_unique_id": None,
            "unit_of_measurement": unit
        }
    
    # Create test entities
    test_entities = [
        make_entity(devices[0]['id'], "sensor.kitchen_temperature_sensor", "Kitchen Temperature Sensor", "temperature", "°C"),
        make_entity(devices[0]['id'], "sensor.kitchen_humidity_sensor", "Kitchen Humidity Sensor", "humidity", "%"),
        make_entity(devices[1]['id'], "sensor.living_room_temperature", "Living Room Temperature", "temperature", "°C"),
        make_entity(devices[2]['id'], "sensor.bedroom_temperature", "Bedroom Temperature", "temperature", "°C"),
        make_entity(devices[3]['id'], "sensor.random_sensor_data", "Random Sensor Data", None, None),
    ]
    
    # Add test entities
    registry['data']['entities'].extend(test_entities)
    
    # Write back
    with open(entity_file, 'w') as f:
        json.dump(registry, f, indent=2)
    
    print(f"✓ Added {len(test_entities)} test entities to entity registry")


def main():
    """Main function."""
    storage_path = Path("/home/alex/Projects/ha_filters/tests/ha_config/.storage")
    
    if not storage_path.exists():
        print(f"❌ Storage path not found: {storage_path}")
        return
    
    print("=== Setting up test data for auto_area_assign ===\n")
    
    # Create areas
    print("Creating areas...")
    create_area_registry(storage_path)
    
    # Create devices
    print("\nCreating devices...")
    devices = update_device_registry(storage_path)
    
    # Create entities
    print("\nCreating entities...")
    update_entity_registry(storage_path, devices)
    
    print("\n✅ Test data setup complete!")
    print("\nExpected behavior after HA restart:")
    print("  • Kitchen Multisensor → should be assigned to Kitchen")
    print("  • Living Room Climate Sensor → should be assigned to Living Room")
    print("  • Bedroom Temperature Sensor → should be assigned to Bedroom")
    print("  • Unassigned Random Sensor → should NOT be assigned (no matching area)")
    print("\nRestart HA with: docker compose restart")


if __name__ == "__main__":
    main()

