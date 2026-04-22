import runpy
from pathlib import Path


def test_pyinstaller_spec_declares_hidden_imports_and_datas():
    root = Path(__file__).resolve().parents[1]
    namespace = runpy.run_path(str(root / "packaging/pyinstaller.spec"))
    hidden = namespace["hidden_imports"]
    datas = namespace["datas"]
    assert "llama_cpp" in hidden
    assert "PySide6.QtWidgets" in hidden
    assert "huggingface_hub" in hidden
    assert any(item[0] == "resources" for item in datas)
