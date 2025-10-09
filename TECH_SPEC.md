# Technical Specification: Home Assistant Integration for Automatic Area Assignment

## Objective
Develop a custom Home Assistant integration that automatically assigns areas to devices and entities based on matching their `object_id` with area aliases, both at system startup and on user request.

## Scope
The integration is designed for Home Assistant users who follow consistent entity naming conventions: entity `object_id` values start with the alias of the corresponding area. The solution must work with any Home Assistant installation that supports custom components.

## Requirements

### 1. Data Sources
- **Area Registry** (`area_registry`): retrieve all areas and their aliases
- **Entity Registry** (`entity_registry`): iterate through all entities to find matches by `object_id`
- **Device Registry** (`device_registry`): check and assign areas to devices

### 2. Area Assignment Algorithm
1. Retrieve all areas and build a `slug(alias) -> area_id` mapping. Include the main area name (slugified) to support matches without explicit aliases.
2. Retrieve all entities from the registry. For each entity:
   - Extract `object_id` from `entity_id` (format: `domain.object_id`)
   - Find a match between `object_id` and any key from the alias map based on the condition "`object_id` starts with alias"
   - If a match is found:
     - **If entity has a device**: check if the device has an assigned area. If not, assign the matched area to the device
     - **If entity has no device**: check if the entity has an assigned area. If not, assign the matched area directly to the entity
   - Check for `auto_area_ignore` label on both entities and devices - skip if present
3. Maintain logging: number of matches found, number of areas assigned, list of skipped items (e.g., entities without `device_id`, items with ignore label).

### 3. Home Assistant Integration
- The integration must run the algorithm at Home Assistant startup (`async_setup` via `hass.async_create_task`)
- Users must be able to re-trigger the process via the registered service `auto_area_assign.refresh`
- Logging must use the standard `logging.getLogger(__name__)` with `INFO` and `DEBUG` levels

### 4. Project Structure
```
custom_components/
  auto_area_assign/
    __init__.py        # integration entry point, algorithm implementation, and service registration
    manifest.json      # integration metadata
```
- `manifest.json` must specify name, version, and dependency on Home Assistant `core` >= 2023.5.0 (version with `area.aliases` support)

### 5. Testing
- Unit tests using `pytest` and Home Assistant fixtures to emulate registries
- Tests must verify:
  1. Area assignment to device when `object_id` starts with an alias
  2. No changes when an area is already assigned
  3. Area assignment to standalone entities (without devices)
  4. Ignoring entities with `auto_area_ignore` label
  5. Ignoring devices with `auto_area_ignore` label

### 6. Documentation
- Add `README.md` describing the integration's purpose, operation, installation, and service usage
- Include examples of entity naming configuration and expected behavior in `README.md`

### 7. Non-Functional Requirements
- Code must comply with PEP 8 standards and Home Assistant style guide
- All asynchronous operations must use available asynchronous Home Assistant APIs
- Avoid blocking calls

## Implementation Stages
1. Create integration structure (`custom_components/auto_area_assign`) and metadata (`manifest.json`)
2. Implement algorithm in `__init__.py`
3. Register service for re-triggering the algorithm
4. Develop tests and configure `pytest`
5. Write documentation in `README.md`
6. Run linters/tests, prepare commit and PR
