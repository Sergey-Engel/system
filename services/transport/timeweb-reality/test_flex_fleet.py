import importlib.util
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location("flex_fleet", Path(__file__).with_name("flex_fleet.py"))
fleet = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fleet)


def state():
    return {"default": {"exit": "fx", "ru_direct": "off"},
            "overrides": {device: {"exit": None, "ru_direct": None} for device in fleet.DEVICES}}


def test_global_change_preserves_device_override(monkeypatch):
    current = state()
    current["overrides"]["iphone12"]["exit"] = "cen"
    calls = []
    monkeypatch.setattr(fleet, "command", lambda device, *args: calls.append((device, args)) or
                        {"exit": args[1], "ru_direct": args[2] == "on", "observed": "ready"})
    monkeypatch.setattr(fleet, "save_state", lambda value: None)
    monkeypatch.setattr(fleet, "status", lambda value: {**value, "counts": {"route_ready": 3, "total": 3}})
    updated = fleet.change(current, "all", "exit", "cen")
    assert updated["default"]["exit"] == "cen"
    assert updated["overrides"]["iphone12"]["exit"] == "cen"
    assert calls == [("macbook", ("switch", "cen", "off")),
                     ("macmini", ("switch", "cen", "off"))]


def test_default_inheritance_is_independent_per_field(monkeypatch):
    current = state()
    current["overrides"]["iphone12"] = {"exit": "cen", "ru_direct": "on"}
    calls = []
    monkeypatch.setattr(fleet, "command", lambda device, *args: calls.append((device, args)) or
                        {"exit": args[1], "ru_direct": args[2] == "on", "observed": "ready"})
    monkeypatch.setattr(fleet, "save_state", lambda value: None)
    monkeypatch.setattr(fleet, "status", lambda value: {**value, "counts": {"route_ready": 3, "total": 3}})
    updated = fleet.change(current, "iphone12", "exit", "default")
    assert fleet.effective(updated, "iphone12") == {"exit": "fx", "ru_direct": "on"}
    assert calls == [("iphone12", ("switch", "fx", "on"))]


def test_second_device_failure_rolls_back_first(monkeypatch):
    current = state()
    calls = []

    def command(device, *args):
        calls.append((device, args))
        if device == "iphone12":
            raise RuntimeError("controller failure")
        return {"exit": args[1], "ru_direct": args[2] == "on", "observed": "ready"}

    monkeypatch.setattr(fleet, "command", command)
    monkeypatch.setattr(fleet, "save_state", lambda value: pytest.fail("state must not be saved"))
    with pytest.raises(RuntimeError):
        fleet.change(current, "all", "exit", "cen")
    assert calls == [("macbook", ("switch", "cen", "off")),
                     ("iphone12", ("switch", "cen", "off")),
                     ("macbook", ("switch", "fx", "off"))]


def test_readback_mismatch_rolls_back_changed_device(monkeypatch):
    current = state()
    calls = []

    def command(device, *args):
        calls.append((device, args))
        return {"exit": "fx", "ru_direct": False, "observed": "ready"}

    monkeypatch.setattr(fleet, "command", command)
    monkeypatch.setattr(fleet, "save_state", lambda value: pytest.fail("state must not be saved"))
    with pytest.raises(RuntimeError, match="read-back mismatch"):
        fleet.change(current, "iphone12", "exit", "cen")
    assert calls == [("iphone12", ("switch", "cen", "off")),
                     ("iphone12", ("switch", "fx", "off"))]
