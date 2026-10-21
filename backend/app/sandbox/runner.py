# backend/app/sandbox/runner.py — Ephemeral Docker Sandbox Runner
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    import docker
except ImportError:
    docker = None

ALLOWED_COMMANDS = {
    "pytest": ["pytest", "-q", "--tb=short", "--disable-warnings"],
    "ruff": ["ruff", "check", "."],
}

class EphemeralSandboxRunner:
    """Executes generated adapter patches inside a network-disabled, non-root container."""
    def __init__(self, image: str = "autopatch/sandbox-py312:1.4", docker_client: Optional[Any] = None):
        self._client = docker_client
        self.image = image

    @property
    def client(self):
        if self._client is None:
            if docker is None:
                raise RuntimeError("The 'docker' Python library is not installed in this environment.")
            self._client = docker.from_env()
        return self._client

    def validate_patch(self, repo_snapshot: Path, planned_files: List[str], modified_files: Dict[str, str]) -> Dict[str, Any]:
        # 1. Explicit Change-Scope Verification
        unexpected = set(modified_files.keys()) - set(planned_files)
        if unexpected:
            raise PermissionError(f"Scope violation: Patch modified unplanned files: {unexpected}")

        with tempfile.TemporaryDirectory(prefix="autopatch_sbx_") as tmpdir:
            work_path = Path(tmpdir)
            shutil.copytree(repo_snapshot, work_path / "repo")
            for rel_path, content in modified_files.items():
                target = (work_path / "repo" / rel_path).resolve()
                if not str(target).startswith(str((work_path / "repo").resolve())):
                    raise PermissionError("Path traversal blocked.")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")

            container = self.client.containers.run(
                image=self.image,
                command=ALLOWED_COMMANDS["pytest"],
                user="10001:10001",          # Non-root execution user
                network_disabled=True,       # Zero outbound internet access
                read_only=True,              # Read-only root filesystem
                mem_limit="256m",            # Strict memory ceiling
                nano_cpus=500_000_000,       # 0.5 CPU ceiling
                pids_limit=64,               # Fork-bomb protection
                cap_drop=["ALL"],            # Drop all Linux capabilities
                security_opt=["no-new-privileges:true"],
                tmpfs={"/tmp": "size=32m,noexec,nosuid"},
                volumes={str(work_path / "repo"): {"bind": "/workspace", "mode": "ro"}},
                working_dir="/workspace",
                detach=True,
            )
            try:
                result = container.wait(timeout=30)
                logs = container.logs().decode("utf-8", errors="replace")
                return {"exit_code": result["StatusCode"], "logs": logs, "scope_verified": True}
            finally:
                container.remove(force=True)
