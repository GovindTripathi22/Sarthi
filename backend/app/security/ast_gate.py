from __future__ import annotations

import ast
from typing import List

FORBIDDEN_MODULES = {
    "subprocess",
    "shutil",
    "socket",
    "ctypes",
    "multiprocessing",
    "pty",
    "ptyprocess",
    "winreg",
}
FORBIDDEN_CALLS = {"eval", "exec", "compile", "__import__", "system", "popen", "spawn"}


def verify_python_ast_security(code_string: str) -> List[str]:
    """
    Parse candidate patch code with Python's `ast` module and reject syntax errors,
    forbidden imports, environment secret scraping, or arbitrary command execution.
    """
    violations: List[str] = []
    try:
        tree = ast.parse(code_string)
    except SyntaxError as exc:
        return [f"SyntaxError at line {exc.lineno}: {exc.msg}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_mod = alias.name.split(".")[0]
                if root_mod in FORBIDDEN_MODULES:
                    violations.append(f"Forbidden import '{alias.name}' in sandbox patch.")
        elif isinstance(node, ast.ImportFrom) and node.module:
            root_mod = node.module.split(".")[0]
            if root_mod in FORBIDDEN_MODULES:
                violations.append(f"Forbidden import from '{node.module}' in sandbox patch.")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                violations.append(f"Forbidden builtin call '{node.func.id}()' detected.")
            elif isinstance(node.func, ast.Attribute) and node.func.attr in FORBIDDEN_CALLS:
                violations.append(f"Forbidden method call '.{node.func.attr}()' detected.")
        elif isinstance(node, ast.Attribute):
            if node.attr == "environ":
                violations.append("Forbidden access to 'os.environ' secrets detected.")

    return violations
