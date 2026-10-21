# backend/tests/test_sandbox_runner.py
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from backend.app.sandbox.runner import EphemeralSandboxRunner, ALLOWED_COMMANDS

def test_allowed_commands():
    assert "pytest" in ALLOWED_COMMANDS
    assert "ruff" in ALLOWED_COMMANDS
    assert ALLOWED_COMMANDS["pytest"][0] == "pytest"
    assert ALLOWED_COMMANDS["ruff"][0] == "ruff"

def test_scope_violation_raises_permission_error():
    runner = EphemeralSandboxRunner(docker_client=MagicMock())
    planned = ["src/adapters/commerce_customer_adapter.py"]
    modified = {
        "src/adapters/commerce_customer_adapter.py": "content",
        "src/config/secrets.py": "exfiltrate_secrets()"
    }
    with pytest.raises(PermissionError) as exc_info:
        runner.validate_patch(Path("/fake/repo"), planned, modified)
    assert "Scope violation" in str(exc_info.value)
    assert "secrets.py" in str(exc_info.value)

def test_path_traversal_raises_permission_error():
    runner = EphemeralSandboxRunner(docker_client=MagicMock())
    planned = ["../../etc/passwd"]
    modified = {"../../etc/passwd": "root:x:0:0:..."}

    with tempfile.TemporaryDirectory() as fake_repo:
        with pytest.raises(PermissionError) as exc_info:
            runner.validate_patch(Path(fake_repo), planned, modified)
        assert "Path traversal blocked" in str(exc_info.value)

def test_successful_mocked_container_run():
    mock_container = MagicMock()
    mock_container.wait.return_value = {"StatusCode": 0}
    mock_container.logs.return_value = b"==== 4 passed in 0.42s ===="

    mock_client = MagicMock()
    mock_client.containers.run.return_value = mock_container

    runner = EphemeralSandboxRunner(docker_client=mock_client)
    planned = ["src/adapters/commerce_customer_adapter.py"]
    modified = {"src/adapters/commerce_customer_adapter.py": "# patched code"}

    with tempfile.TemporaryDirectory() as fake_repo:
        repo_dir = Path(fake_repo) / "src" / "adapters"
        repo_dir.mkdir(parents=True)
        (repo_dir / "commerce_customer_adapter.py").write_text("# initial code")

        result = runner.validate_patch(Path(fake_repo), planned, modified)
        assert result["exit_code"] == 0
        assert "4 passed" in result["logs"]
        assert result["scope_verified"] is True
        mock_container.remove.assert_called_once_with(force=True)
