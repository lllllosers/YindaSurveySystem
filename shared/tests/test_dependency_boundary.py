import ast
from pathlib import Path


def test_shared_has_no_product_framework_or_persistence_dependencies():
    forbidden = {"desktop", "web", "web_center", "PySide6", "fastapi", "sqlalchemy", "sqlite3", "database", "forms", "services", "pages", "app"}
    paths = list(Path(__file__).resolve().parents[1].rglob("*.py"))
    assert paths
    violations = []
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            modules = [alias.name for alias in node.names] if isinstance(node, ast.Import) else ([node.module] if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module else [])
            for module in modules:
                if module.split(".")[0] in forbidden:
                    violations.append(f"{path.name}:{node.lineno}:{module}")
    assert not violations, violations
