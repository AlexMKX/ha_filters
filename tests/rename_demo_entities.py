#!/usr/bin/env python3
"""Rename demo entities to match area prefixes."""
import json
from pathlib import Path

storage_path = Path("/home/alex/Projects/ha_filters/tests/ha_config/.storage")
device_file = storage_path / "core.device_registry"
entity_file = storage_path / "core.entity_registry"

# Read registries
with open(device_file, 'r') as f:
    devices = json.load(f)

with open(entity_file, 'r') as f:
    entities = json.load(f)

# Find devices without area_id
unassigned_devices = [d for d in devices['data']['devices'] if d.get('area_id') is None and d.get('name') not in ['Backup', 'Sun']][:4]

print(f"Found {len(unassigned_devices)} unassigned devices\n")

# Map devices to new prefixes
prefix_map = {
    0: ("kitchen", "Kitchen"),
    1: ("living_room", "Living Room"),
    2: ("bedroom", "Bedroom"),
    3: ("bathroom", "Bathroom")
}

renamed_count = 0

for idx, device in enumerate(unassigned_devices[:4]):
    if idx not in prefix_map:
        break
    
    prefix, area_name = prefix_map[idx]
    device_id = device['id']
    device_name = device['name']
    
    print(f"Device: {device_name} (ID: {device_id})")
    
    # Find entities for this device
    device_entities = [e for e in entities['data']['entities'] if e.get('device_id') == device_id]
    
    for entity in device_entities:
        old_entity_id = entity['entity_id']
        domain, object_id = old_entity_id.split('.', 1)
        new_entity_id = f"{domain}.{prefix}_{object_id}"
        
        entity['entity_id'] = new_entity_id
        renamed_count += 1
        print(f"  ✓ Renamed: {old_entity_id} → {new_entity_id}")
    
    print()

# Write back
with open(entity_file, 'w') as f:
    json.dump(entities, f, indent=2)

print(f"\n✅ Renamed {renamed_count} entities!")
print("Expected behavior after HA restart:")
print("  • Devices should be automatically assigned to matching areas")

