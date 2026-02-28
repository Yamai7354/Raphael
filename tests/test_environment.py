import pytest
import os
import aiofiles
import asyncio
from src.raphael.environment.constraints import SandboxConfig
from src.raphael.environment.filesystem import SecureFileSystem
from src.raphael.environment.network import NetworkAccessor
from src.raphael.environment.monitor import SystemMonitor
from src.raphael.core.event_bus import SystemEventBus
from src.raphael.core.schemas import EventType


async def test_sandbox_constraints_paths():
    # Allow only the /tmp directory limit
    config = SandboxConfig(allowed_directories=["/tmp/raphael_sandbox_test"])

    # Valid paths inside
    assert config.is_path_allowed("/tmp/raphael_sandbox_test/file.txt") is True
    assert config.is_path_allowed("/tmp/raphael_sandbox_test/deep/dir/file.log") is True

    # Invalid paths outside
    assert config.is_path_allowed("/etc/passwd") is False
    assert config.is_path_allowed("/Users/someone/Desktop") is False


async def test_secure_file_system_read_write(tmp_path):
    # tmp_path is provided natively by pytest
    config = SandboxConfig(allowed_directories=[str(tmp_path)])
    fs = SecureFileSystem(config)

    test_file = str(tmp_path / "test_write.txt")
    test_content = "Raphael Layer 1 Initialization"

    # 1. Write file
    written_path = await fs.write_file(test_file, test_content)
    assert written_path == test_file

    # 2. Read file
    read_content = await fs.read_file(test_file)
    assert read_content == test_content


async def test_secure_file_system_blocks_escape():
    config = SandboxConfig(allowed_directories=["/tmp/raphael_sandbox"])
    fs = SecureFileSystem(config)

    with pytest.raises(PermissionError) as exc_info:
        await fs.read_file("/etc/hosts")
    assert "outside the allowed sandbox" in str(exc_info.value)


async def test_network_accessor_domain_blocking():
    config = SandboxConfig(blocked_domains=["localhost", "baddomain.com"])
    network = NetworkAccessor(config)

    # Valid external URL
    network._validate_url("https://api.github.com/v1")

    # Blocked Localhost
    with pytest.raises(PermissionError):
        network._validate_url("http://localhost:8080/api")

    # Blocked explicit domain
    with pytest.raises(PermissionError):
        network._validate_url("https://baddomain.com/hack")


async def test_system_monitor_emits_telemetry():
    bus = SystemEventBus()
    monitor = SystemMonitor(bus=bus, poll_interval=60.0)

    captured_events = []

    async def trap_event(event):
        captured_events.append(event)

    bus.subscribe(EventType.OBSERVATION, trap_event)
    await bus.start()

    # Manually trigger one run instead of starting the loop to avoid test hanging
    await monitor.emit_telemetry()
    await asyncio.sleep(0.1)  # Let the queue process

    assert len(captured_events) == 1
    event = captured_events[0]
    assert event.event_type == EventType.OBSERVATION
    assert event.source_layer.module_name == "SystemMonitor"
    assert "cpu_percent" in event.payload["data"]

    await bus.stop()


async def run_all_tests():
    import pathlib

    print("Running Environment Layer 1 tests natively...")

    await test_sandbox_constraints_paths()
    print("test_sandbox_constraints_paths: PASSED")

    import tempfile

    with tempfile.TemporaryDirectory() as temp_dir:
        tmp = pathlib.Path(temp_dir)
        await test_secure_file_system_read_write(tmp)
        print("test_secure_file_system_read_write: PASSED")

    await test_secure_file_system_blocks_escape()
    print("test_secure_file_system_blocks_escape: PASSED")

    await test_network_accessor_domain_blocking()
    print("test_network_accessor_domain_blocking: PASSED")

    await test_system_monitor_emits_telemetry()
    print("test_system_monitor_emits_telemetry: PASSED")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
