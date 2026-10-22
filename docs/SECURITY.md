# Security & Governance Policy — Sarthi / AutoPatch

## 1. Threat Model & Security Posture

Sarthi operates as an inline API proxy with autonomous code-generation capabilities. Because it processes untrusted upstream network payloads and executes generated Python code, security boundaries are strictly enforced across multiple defense layers.

---

## 2. Security Defense Layers

### Layer 1: Anti-SSRF (Server-Side Request Forgery) Gateway
- **Protocol Restriction**: Only `http://` and `https://` schemes are permitted.
- **IP Address Traps**: Evaluates resolved destination IP addresses:
  - Blocks AWS/GCP Instance Metadata Service (`169.254.169.254` and `fd00:ec2::254`).
  - Blocks Link-Local addresses (`169.254.0.0/16`).
  - Blocks Private subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) in production.
  - Blocks Loopback addresses (`127.0.0.0/8`, `::1`) in production.
- **Path Traversal Protection**: Rejects URLs containing directory traversal attempts (`..`).

### Layer 2: AST Security Static Code Analysis
Before any generated patch or code artifact can be placed into the sandbox or reviewed by a human, it must pass static Python Abstract Syntax Tree (AST) inspection (`verify_python_ast_security`):
- **Forbidden Modules**: `subprocess`, `shutil`, `socket`, `ctypes`, `multiprocessing`, `pty`, `ptyprocess`, `winreg`.
- **Forbidden Builtin Calls**: `eval()`, `exec()`, `compile()`, `__import__()`, `os.system()`, `os.popen()`.
- **Secret Scraping**: Prohibits any reference to `os.environ`.
Any violation immediately aborts execution and logs a security violation incident.

### Layer 3: Ephemeral Isolated Sandbox
- Executes candidate adapter code in a disposable `tempfile.TemporaryDirectory`.
- Environment variables are stripped down to sanitized system variables.
- Memory, CPU, and execution timeouts (15 seconds) are enforced.
- Never mounts secret credentials or host files into execution workspaces.

### Layer 4: Role-Based Access Control (RBAC)
Server-side verified role enforcement (`require_roles`):
- **Viewer**: Read-only access to dashboards, integrations, and incidents. Cannot approve patches or authorize deployments.
- **Engineer**: Can view code diffs, run repairs, request patch revisions, and create PRs.
- **Reviewer**: Can approve or reject repair proposals at Node 9.
- **Admin**: Full authority including registering connectors, approving repairs, and authorizing production deployments.

### Layer 5: Immutable Governance Audit Log
All sensitive events (registrations, updates, review decisions, deployment authorizations, and unauthorized 403 blocks) are written to the append-only `audit_logs` table with actor, role, action, target, and timestamp.
