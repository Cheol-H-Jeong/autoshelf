import ast
from pathlib import Path

from autoshelf.gui.icons import available_icons


def test_icon_references_resolve_to_bundled_svg():
    root = Path(__file__).resolve().parents[1] / "autoshelf/gui"
    names: set[str] = set()
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "icon":
                if (
                    node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                ):
                    names.add(node.args[0].value)
    assert names <= available_icons()
