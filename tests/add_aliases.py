#!/usr/bin/env python3
"""Add aliases to existing areas."""
import json
from pathlib import Path

storage_path = Path("/home/alex/Projects/ha_filters/tests/ha_config/.storage")
area_file = storage_path / "core.area_registry"

with open(area_file, 'r') as f:
    data = json.load(f)

# Add aliases to areas
alias_map = {
    "Kitchen": ["kitchen", "кухня"],
    "Living Room": ["living_room", "гостиная"],
    "Bedroom": ["bedroom", "спальня"],
    "Bathroom": ["bathroom", "ванная"]
}

for area in data['data']['areas']:
    if area['name'] in alias_map:
        area['aliases'] = alias_map[area['name']]
        print(f"✓ Added aliases to {area['name']}: {area['aliases']}")

with open(area_file, 'w') as f:
    json.dump(data, f, indent=2)

print("\n✅ Aliases added successfully!")

