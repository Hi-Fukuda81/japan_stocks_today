import copy
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / ".claude" / "skills" / "evening-disclosure-script"
EXAMPLES = SKILL / "examples"


def _load_validate_module():
    spec = importlib.util.spec_from_file_location("validate", SKILL / "scripts" / "validate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def validate_mod():
    return _load_validate_module()


@pytest.fixture(scope="session")
def _example_data():
    return json.loads((EXAMPLES / "2026-11-13.data.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def _example_script():
    return json.loads((EXAMPLES / "2026-11-13.json").read_text(encoding="utf-8"))


@pytest.fixture
def example_data(_example_data):
    return copy.deepcopy(_example_data)


@pytest.fixture
def example_script(_example_script):
    return copy.deepcopy(_example_script)


@pytest.fixture
def day_dir(tmp_path, example_data, example_script):
    d = tmp_path / "2026-11-13"
    d.mkdir()
    (d / "data.json").write_text(json.dumps(example_data, ensure_ascii=False), encoding="utf-8")
    (d / "script.json").write_text(json.dumps(example_script, ensure_ascii=False), encoding="utf-8")
    return d
