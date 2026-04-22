import importlib.util
from pathlib import Path

from autoshelf import __version__


def _build_module():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "autoshelf_packaging_build", root / "packaging/build.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inno_setup_template_contains_required_directives(tmp_path):
    root = Path(__file__).resolve().parents[1]
    text = (root / "packaging/windows/autoshelf.iss").read_text(encoding="utf-8")
    assert "AppId=" in text
    assert 'AppVersion={#AppVersion}' in text
    assert "OutputBaseFilename=autoshelf-{#AppVersion}-win-x64-setup" in text
    assert "LicenseFile=" in text
    assert "사용자 설정 및 다운로드한 모델도 삭제" in text
    assert "autoshelf plan" in text
    rendered = _build_module().render_inno_script(root, __version__, tmp_path / "autoshelf.iss")
    rendered_text = rendered.read_text(encoding="utf-8")
    assert f'#define AppVersion "{__version__}"' in rendered_text


def test_inno_file_association_is_registered():
    root = Path(__file__).resolve().parents[1]
    text = (root / "packaging/windows/autoshelf.iss").read_text(encoding="utf-8")
    assert ".autoshelf-plan" in text
    assert "apply --resume" in text
