# Auto Area Assign

A custom Home Assistant integration that automatically assigns areas to devices and entities based on their `object_id` prefix matching area aliases.

## Features
- Builds a mapping table based on area names and aliases
- Automatically assigns areas to **devices** with matching entity prefixes
- Automatically assigns areas to **standalone entities** (entities without devices)
- Ignores entities and devices with the `auto_area_ignore` label
- Safely handles cases where devices or entities already have an assigned area
- Manual refresh via Home Assistant service

## Installation
1. Copy the `custom_components/auto_area_assign` directory to your Home Assistant's `custom_components` directory
2. Restart Home Assistant

## Usage
- The integration automatically runs the algorithm when Home Assistant starts
- For manual execution, use the `auto_area_assign.refresh` service from Developer Tools → Services

## Naming Requirements
- Entity `object_id` values must start with the slugified version of an area name or alias. For example, if you have an area named "Kitchen" with alias `kitchen`, entities like `light.kitchen_ceiling` or `switch.kitchen_socket` will have their devices assigned to the "Kitchen" area.

## Ignoring Entities and Devices
You can exclude entities or devices from automatic assignment by adding the **`auto_area_ignore`** label:

1. **For standalone entities**: navigate to the entity settings and add the `auto_area_ignore` label
2. **For devices**: navigate to the device settings and add the `auto_area_ignore` label

All entities linked to a device with the `auto_area_ignore` label will also be ignored.

## Development
Implementation details and roadmap are available in [TECH_SPEC.md](TECH_SPEC.md).
