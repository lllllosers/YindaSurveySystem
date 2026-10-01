import ast
from pathlib import Path


def test_web_has_no_desktop_source_dependency():
    web_root = Path(__file__).resolve().parents[2]
    paths = list((web_root / "backend/app").rglob("*.py")) + list(web_root.glob("*.py"))
    assert paths
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(text)):
            modules = [alias.name for alias in node.names] if isinstance(node, ast.Import) else ([node.module] if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module else [])
            assert not {name.split(".")[0] for name in modules} & {"desktop", "forms", "services", "database", "pages"}, str(path)
        assert "DESKTOP_SRC" not in text
        assert 'REPO_ROOT / "src"' not in text
