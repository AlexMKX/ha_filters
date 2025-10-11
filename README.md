# Home Assistant Custom Components

A collection of custom Home Assistant integrations for automation and device management.

## Components

### Auto Area Assign

Automatically assigns areas to devices and entities based on their `object_id` prefix matching area aliases.

### Climate Sync

Synchronizes external temperature sensors with TRVZB (thermostatic radiator valve) devices, enabling precise climate control using room temperature sensors instead of internal TRV sensors.

---

## Auto Area Assign

### Features
- Builds a mapping table based on area names and aliases
- Automatically assigns areas to **devices** with matching entity prefixes
- Automatically assigns areas to **standalone entities** (entities without devices)
- Ignores entities and devices with the `auto_area_ignore` label
- Safely handles cases where devices or entities already have an assigned area
- Manual refresh via Home Assistant service

### Installation
1. Copy the `custom_components/auto_area_assign` directory to your Home Assistant's `custom_components` directory
2. Add `auto_area_assign:` to your `configuration.yaml`
3. Restart Home Assistant

### Usage
- The integration automatically runs the algorithm when Home Assistant starts
- For manual execution, use the `auto_area_assign.refresh` service from Developer Tools → Services

### Naming Requirements
- Entity `object_id` values must start with the slugified version of an area name or alias. For example, if you have an area named "Kitchen" with alias `kitchen`, entities like `light.kitchen_ceiling` or `switch.kitchen_socket` will have their devices assigned to the "Kitchen" area.

### Ignoring Entities and Devices
You can exclude entities or devices from automatic assignment by adding the **`auto_area_ignore`** label:

1. **For standalone entities**: navigate to the entity settings and add the `auto_area_ignore` label
2. **For devices**: navigate to the device settings and add the `auto_area_ignore` label

All entities linked to a device with the `auto_area_ignore` label will also be ignored.

---

## Climate Sync

### Features
- Automatically discovers TRVZB (Zigbee thermostatic radiator valve) devices in areas
- Uses area-assigned temperature sensors for accurate climate control
- Sets TRVZB devices to "external" temperature sensor mode
- Real-time synchronization when temperature changes
- Periodic synchronization every 10 minutes as backup
- Only updates when temperature actually changes (efficient)
- Supports dynamic device addition during runtime
- Standard Home Assistant service calls (no direct MQTT/ZHA manipulation)

### How It Works
1. **Discovery**: Finds all TRVZB devices (by model_id "TRVZB") in areas that have assigned temperature sensors
2. **Setup**: Configures each TRVZB to use external temperature sensor mode
3. **Sync**: Monitors area temperature sensors and updates TRVZB external temperature values
4. **Smart Updates**: Only sends updates when temperature actually changes (tolerance: 0.05°C)

### Requirements
- TRVZB devices (e.g., SONOFF Zigbee thermostatic radiator valves)
- Temperature sensors assigned to areas via Home Assistant UI
- Home Assistant 2024.8+ (requires `area.temperature_entity_id` support)

### Installation
1. Copy the `custom_components/climate_sync` directory to your Home Assistant's `custom_components` directory
2. Add `climate_sync:` to your `configuration.yaml`
3. Restart Home Assistant

### Configuration
No additional configuration needed! The component automatically:
- Finds all TRVZB devices in areas with temperature sensors
- Sets up listeners for temperature changes
- Manages synchronization automatically

### Assigning Temperature Sensors to Areas
1. Go to Settings → Areas, Devices & Services → Areas
2. Select an area
3. Under "Preferred sensors", assign a temperature sensor
4. The component will automatically use this sensor for all TRVZB devices in that area

### Manual Control
Use the `climate_sync.refresh` service to manually trigger:
- Device rediscovery
- External mode setup
- Temperature synchronization

### Supported Devices
- SONOFF TRVZB (tested)
- Any Zigbee thermostatic radiator valve with model_id "TRVZB" should work

### Example Logs
```
[custom_components.climate_sync] Discovered 3 TRVZB devices
[custom_components.climate_sync] Registered TRVZB device f1-kitchen-trv in area Kitchen
[custom_components.climate_sync] Setup listener for sensor.kitchen_temperature covering 1 TRVZB devices
[custom_components.climate_sync] Syncing f1-kitchen-trv: 24.7°C -> 24.6°C
```

