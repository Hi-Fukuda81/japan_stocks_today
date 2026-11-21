import json
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from src.config import DayPaths
from src.script import runner

CFG = {"script": {"skill": "evening-disclosure-script", "max_turns": 5, "timeout_sec": 10}}


@pytest.fixture
def setup(monkeypatch, tmp_path, day_dir):
    """tmp_path/output/2026-11-13 に data.json だけを置き、claude -p をモックにする。"""
    out = tmp_path / "output"
    out.mkdir()
    target = out / "2026-11-13"
    target.mkdir()
    shutil.copy(day_dir / "data.json", target / "data.json")
    monkeypatch.setattr(runner, "load_config", lambda: CFG)
    monkeypatch.setattr(runner.DayPaths, "for_date", classmethod(lambda cls, d: DayPaths(out / d)))
    calls = []
    real_run = subprocess.run

    def fake_run(cmd, **kwargs):
        if cmd[0] != "claude":
            return real_run(cmd, **kwargs)
        calls.append((cmd, kwargs))
        behavior = setup.behaviors.pop(0)
        return behavior(target)

    setup.behaviors = []
    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    return SimpleNamespace(target=target, calls=calls, source=day_dir, behaviors=setup.behaviors)


def ok_result():
    return SimpleNamespace(returncode=0, stdout=json.dumps({"is_error": False, "result": "OK", "num_turns": 3}),
                           stderr="")


def writes(script_text):
    def behavior(target):
        (target / "script.json").write_text(script_text, encoding="utf-8")
        return ok_result()
    return behavior


def test_success(setup):
    good = (setup.source / "script.json").read_text(encoding="utf-8")
    setup.behaviors.append(writes(good))
    path = runner.run_script_skill("2026-11-13")
    assert path == setup.target / "script.json"
    cmd, kwargs = setup.calls[0]
    assert cmd[:3] == ["claude", "-p", "/evening-disclosure-script 2026-11-13"]
    assert "ANTHROPIC_API_KEY" not in kwargs["env"]
    assert "WebSearch" in cmd[cmd.index("--disallowedTools") + 1]


def test_final_gate_rejects_and_retries(setup):
    good = json.loads((setup.source / "script.json").read_text(encoding="utf-8"))
    bad = {**good, "title": "おすすめ銘柄まとめ"}
    setup.behaviors += [writes(json.dumps(bad, ensure_ascii=False)), writes(json.dumps(good, ensure_ascii=False))]
    assert runner.run_script_skill("2026-11-13").exists()
    assert len(setup.calls) == 2


def test_fails_after_attempts(setup):
    setup.behaviors += [lambda t: ok_result(), lambda t: ok_result()]
    with pytest.raises(runner.ScriptGenerationError, match="script.json が作られませんでした"):
        runner.run_script_skill("2026-11-13")


def test_claude_error_raises(setup):
    err = lambda t: SimpleNamespace(returncode=1, stdout="", stderr="usage limit reached")  # noqa: E731
    setup.behaviors += [err, err]
    with pytest.raises(runner.ScriptGenerationError, match="usage limit"):
        runner.run_script_skill("2026-11-13")


def test_missing_data_json(setup):
    (setup.target / "data.json").unlink()
    with pytest.raises(runner.ScriptGenerationError, match="data.json がありません"):
        runner.run_script_skill("2026-11-13")


def test_child_env_strips_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert "ANTHROPIC_API_KEY" not in runner.child_env()


def test_claude_error_then_success_retries(setup):
    good = (setup.source / "script.json").read_text(encoding="utf-8")
    setup.behaviors += [
        lambda t: SimpleNamespace(returncode=0, stdout=json.dumps({"is_error": True, "result": "max turns"}), stderr=""),
        writes(good),
    ]
    assert runner.run_script_skill("2026-11-13").exists()
    assert len(setup.calls) == 2


def test_read_permission_is_scoped():
    assert "Read" not in runner.ALLOWED_TOOLS
    assert "Read(.env)" in runner.DISALLOWED_TOOLS
