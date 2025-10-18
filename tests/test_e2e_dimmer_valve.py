"""End-to-end tests for the Dimmer Valve integration using Docker."""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest
import requests


DOCKER_COMPOSE_FILE = Path(__file__).parent / "docker-compose.yml"
CONTAINER_NAME = "ha_test"
HA_URL = "http://localhost:8123"
API_HEADERS = {"Authorization": "Bearer your_token_here"}


def run_docker_command(command: list[str]) -> tuple[int, str, str]:
    """Run a docker exec command."""
    full_command = ["docker", "exec", CONTAINER_NAME] + command
    result = subprocess.run(
        full_command, capture_output=True, text=True, timeout=30
    )
    return result.returncode, result.stdout, result.stderr


def wait_for_ha_ready(timeout: int = 60) -> bool:
    """Wait for Home Assistant to be ready."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"{HA_URL}/api/", timeout=5)
            # API returns 401 when it's ready but requires auth
            if response.status_code in (200, 401):
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(2)
    return False


def get_entity_state(entity_id: str) -> dict | None:
    """Get entity state via REST API."""
    try:
        response = requests.get(
            f"{HA_URL}/api/states/{entity_id}",
            timeout=5,
        )
        if response.status_code == 200:
            return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error getting entity state: {e}")
    return None


def set_entity_state(entity_id: str, service: str, **kwargs) -> bool:
    """Call a service on an entity."""
    domain = entity_id.split(".")[0]
    try:
        response = requests.post(
            f"{HA_URL}/api/services/{domain}/{service}",
            json={"entity_id": entity_id, **kwargs},
            timeout=5,
        )
        return response.status_code in (200, 201)
    except requests.exceptions.RequestException as e:
        print(f"Error calling service: {e}")
        return False


def get_entity_registry() -> dict:
    """Get entity registry data via docker exec."""
    returncode, stdout, stderr = run_docker_command(
        ["cat", "/config/.storage/core.entity_registry"]
    )
    if returncode == 0:
        return json.loads(stdout)
    return {}


def check_entity_hidden(entity_id: str) -> bool:
    """Check if entity is hidden."""
    registry = get_entity_registry()
    for entry in registry.get("data", {}).get("entities", []):
        if entry.get("entity_id") == entity_id:
            return entry.get("hidden_by") == "integration"
    return False


@pytest.fixture(scope="module")
def docker_ha():
    """Start Home Assistant in Docker."""
    # Start docker compose
    subprocess.run(
        ["docker", "compose", "-f", str(DOCKER_COMPOSE_FILE), "up", "-d"],
        check=True,
        cwd=DOCKER_COMPOSE_FILE.parent,
    )
    
    # Wait for HA to be ready
    if not wait_for_ha_ready(timeout=120):
        # Stop docker compose
        subprocess.run(
            ["docker", "compose", "-f", str(DOCKER_COMPOSE_FILE), "down"],
            cwd=DOCKER_COMPOSE_FILE.parent,
        )
        pytest.fail("Home Assistant did not start in time")
    
    # Give HA some time to fully initialize
    time.sleep(10)
    
    yield
    
    # Cleanup: stop docker compose
    subprocess.run(
        ["docker", "compose", "-f", str(DOCKER_COMPOSE_FILE), "down", "-v"],
        cwd=DOCKER_COMPOSE_FILE.parent,
    )


def test_valve_entities_created(docker_ha):
    """Test that valve entities are created from light entities."""
    # Check that valve entities exist
    valve1_state = get_entity_state("valve.ceiling_lights")
    valve2_state = get_entity_state("valve.bed_light")
    
    assert valve1_state is not None, "valve.ceiling_lights should exist"
    assert valve2_state is not None, "valve.bed_light should exist"
    
    print(f"Valve 1 state: {valve1_state}")
    print(f"Valve 2 state: {valve2_state}")


def test_light_entities_hidden(docker_ha):
    """Test that source light entities are hidden."""
    time.sleep(5)  # Wait for integration to hide lights
    
    assert check_entity_hidden("light.ceiling_lights"), "light.ceiling_lights should be hidden"
    assert check_entity_hidden("light.bed_light"), "light.bed_light should be hidden"


def test_normally_open_sync_light_to_valve(docker_ha):
    """Test normally_open: light brightness -> valve position sync."""
    # Set light brightness to 100% (valve should be 0% - closed)
    assert set_entity_state("light.ceiling_lights", "turn_on", brightness=255)
    time.sleep(2)
    
    valve_state = get_entity_state("valve.ceiling_lights")
    assert valve_state is not None
    position = valve_state.get("attributes", {}).get("current_position")
    assert position == 0, f"NO valve at 100% brightness should be 0% open, got {position}"
    
    # Set light brightness to 0% (valve should be 100% - open)
    assert set_entity_state("light.ceiling_lights", "turn_off")
    time.sleep(2)
    
    valve_state = get_entity_state("valve.ceiling_lights")
    assert valve_state is not None
    position = valve_state.get("attributes", {}).get("current_position")
    assert position == 100, f"NO valve at 0% brightness should be 100% open, got {position}"
    
    # Set light brightness to 50% (valve should be ~50%)
    assert set_entity_state("light.ceiling_lights", "turn_on", brightness=128)
    time.sleep(2)
    
    valve_state = get_entity_state("valve.ceiling_lights")
    assert valve_state is not None
    position = valve_state.get("attributes", {}).get("current_position")
    assert 45 <= position <= 55, f"NO valve at 50% brightness should be ~50% open, got {position}"


def test_normally_closed_sync_light_to_valve(docker_ha):
    """Test normally_closed: light brightness -> valve position sync."""
    # Set light brightness to 100% (valve should be 100% - open)
    assert set_entity_state("light.bed_light", "turn_on", brightness=255)
    time.sleep(2)
    
    valve_state = get_entity_state("valve.bed_light")
    assert valve_state is not None
    position = valve_state.get("attributes", {}).get("current_position")
    assert position == 100, f"NC valve at 100% brightness should be 100% open, got {position}"
    
    # Set light brightness to 0% (valve should be 0% - closed)
    assert set_entity_state("light.bed_light", "turn_off")
    time.sleep(2)
    
    valve_state = get_entity_state("valve.bed_light")
    assert valve_state is not None
    position = valve_state.get("attributes", {}).get("current_position")
    assert position == 0, f"NC valve at 0% brightness should be 0% open, got {position}"


def test_valve_control_updates_light_no(docker_ha):
    """Test valve control updates light brightness for normally_open."""
    # Open valve (position 100) -> light should be off (brightness 0)
    assert set_entity_state("valve.ceiling_lights", "open_valve")
    time.sleep(2)
    
    light_state = get_entity_state("light.ceiling_lights")
    assert light_state is not None
    assert light_state.get("state") == "off", "NO valve open should turn light off"
    
    # Close valve (position 0) -> light should be on (brightness 255)
    assert set_entity_state("valve.ceiling_lights", "close_valve")
    time.sleep(2)
    
    light_state = get_entity_state("light.ceiling_lights")
    assert light_state is not None
    assert light_state.get("state") == "on", "NO valve close should turn light on"
    brightness = light_state.get("attributes", {}).get("brightness")
    assert brightness == 255, f"NO valve closed should have light brightness 255, got {brightness}"


def test_valve_control_updates_light_nc(docker_ha):
    """Test valve control updates light brightness for normally_closed."""
    # Open valve (position 100) -> light should be on (brightness 255)
    assert set_entity_state("valve.bed_light", "open_valve")
    time.sleep(2)
    
    light_state = get_entity_state("light.bed_light")
    assert light_state is not None
    assert light_state.get("state") == "on", "NC valve open should turn light on"
    brightness = light_state.get("attributes", {}).get("brightness")
    assert brightness == 255, f"NC valve open should have light brightness 255, got {brightness}"
    
    # Close valve (position 0) -> light should be off
    assert set_entity_state("valve.bed_light", "close_valve")
    time.sleep(2)
    
    light_state = get_entity_state("light.bed_light")
    assert light_state is not None
    assert light_state.get("state") == "off", "NC valve close should turn light off"


def test_valve_set_position(docker_ha):
    """Test setting valve position directly."""
    # Set valve to 75%
    assert set_entity_state("valve.ceiling_lights", "set_valve_position", position=75)
    time.sleep(2)
    
    valve_state = get_entity_state("valve.ceiling_lights")
    assert valve_state is not None
    position = valve_state.get("attributes", {}).get("current_position")
    assert position == 75, f"Valve position should be 75%, got {position}"
    
    # For NO: 75% valve = 25% brightness
    light_state = get_entity_state("light.ceiling_lights")
    assert light_state is not None
    brightness = light_state.get("attributes", {}).get("brightness", 0)
    expected_brightness = int((25 / 100) * 255)
    assert abs(brightness - expected_brightness) <= 5, \
        f"NO valve 75% should have light brightness ~{expected_brightness}, got {brightness}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

