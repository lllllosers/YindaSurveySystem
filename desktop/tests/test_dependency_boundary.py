import ast
from pathlib import Path


def test_desktop_has_no_web_source_dependency():
    paths = list((Path(__file__).resolve().parents[1] / "src").rglob("*.py"))
    assert paths
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            modules = [alias.name for alias in node.names] if isinstance(node, ast.Import) else ([node.module] if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module else [])
            assert not {name.split(".")[0] for name in modules} & {"web", "web_center", "app", "fastapi", "sqlalchemy"}, str(path)
