"""Basic integration tests for Dimmer Valve component."""
import subprocess
import time
from pathlib import Path


def test_component_loads_successfully():
    """Test that the dimmer_valve component loads without errors."""
    compose_file = Path(__file__).parent / "docker-compose.yml"
    
    # Start Home Assistant
    subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "up", "-d"],
        check=True,
        cwd=compose_file.parent,
    )
    
    # Wait for initialization
    time.sleep(60)
    
    try:
        # Get logs
        result = subprocess.run(
            ["docker", "logs", "ha_test"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        logs = result.stdout + result.stderr
        
        # Check for successful component setup
        assert "Setting up dimmer_valve" in logs
        assert "Dimmer Valve configuration loaded with 2 dimmers" in logs
        assert "Created valve valve.ceiling_lights from dimmer light.ceiling_lights" in logs
        assert "Created valve valve.bed_light from dimmer light.bed_light" in logs
        
        # Check that entities are registered
        assert "Registered new valve.dimmer_valve entity: valve.ceiling_lights" in logs
        assert "Registered new valve.dimmer_valve entity: valve.bed_light" in logs
        
        # Check for sync
        assert "Updated valve.ceiling_lights from dimmer" in logs
        assert "Updated valve.bed_light from dimmer" in logs
        
        # Check that lights are hidden
        assert "Hidden light entity light.ceiling_lights" in logs
        assert "Hidden light entity light.bed_light" in logs
        
        # Check for no errors
        assert "ERROR (MainThread) [custom_components.dimmer_valve]" not in logs
        
        print("✓ Component loaded successfully")
        print("✓ Valve entities created")
        print("✓ Synchronization working")
        print("✓ Light entities hidden")
        
    finally:
        # Cleanup
        subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "down", "-v"],
            cwd=compose_file.parent,
        )


if __name__ == "__main__":
    test_component_loads_successfully()
    print("\n✓ All basic tests passed!")



