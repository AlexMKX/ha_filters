# Changelog

## [Unreleased]

## climate_sync 0.1.1 - 2025-10-18

### Fixed
- Fixed issue where TRVZB devices with "unknown" temperature state were not being synchronized with area temperature sensors. Now the component will push the correct temperature even when the current device state is unknown or unavailable.

## [0.2.1] - 2025-10-10

### Fixed
- Added missing `services.yaml` file to fix Home Assistant startup errors

## [0.2.0] - 2025-10-10

### Added
- **Area assignment for standalone entities**: The component now automatically assigns areas not only to devices but also to standalone entities (entities without device_id)
- **Support for auto_area_ignore label**: Added ability to exclude entities and devices from automatic assignment using the `auto_area_ignore` label
  - Entities with `auto_area_ignore` label are ignored
  - Devices with `auto_area_ignore` label are ignored (including all their entities)
- **5 new e2e tests** for the new functionality:
  - `test_assigns_area_to_entity_without_device` - positive test for assigning area to standalone entity
  - `test_does_not_assign_entity_without_device_with_existing_area` - negative test: does not override existing entity area
  - `test_ignores_entity_with_auto_area_ignore_label` - test for ignoring entity with label
  - `test_ignores_device_with_auto_area_ignore_label` - test for ignoring device with label
  - `test_assigns_entity_without_device_and_ignores_device_with_label_in_same_run` - complex integration test

### Changed
- Improved logging: now shows separate statistics for devices and entities
- Updated execution statistics: added counter for ignored items

### Technical
- Updated unit tests to support new fields (`labels`, `area_id` for entities)
- Added `run_tests.sh` script for running unit and e2e tests separately

## [0.1.0] - Initial Release
- Basic functionality for assigning areas to devices based on entity name prefixes
- Support for area aliases
- `auto_area_assign.refresh` service for manual execution
