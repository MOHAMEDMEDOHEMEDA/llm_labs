import gradio as gr
import pytest

from week2_flightai.__main__ import main
from week2_flightai.app import build_ui, cancel_booking, confirm_booking, pending_table
from week2_flightai.assistant import Assistant
from week2_flightai.config import SYSTEM_PROMPT, Settings
from week2_flightai.tools import flight_tools


def test_confirm_button_logic_completes_only_pending_bookings(store):
    booking = store.request_booking("London", "Sara Ali")
    assert pending_table(store) == [[booking.ref, "Sara Ali", "London", "$799"]]

    assert confirm_booking(store, booking.ref).startswith(f"Confirmed {booking.ref}")
    assert pending_table(store) == []
    assert "already confirmed" in confirm_booking(store, booking.ref)
    assert confirm_booking(store, None) == "Choose a booking to confirm."
    assert "No booking with reference" in cancel_booking(store, "FA-XXXXXX")


def test_ui_builds_without_launching(store, scripted):
    bot = Assistant(scripted([]), flight_tools(store), SYSTEM_PROMPT)
    assert isinstance(build_ui(bot, store), gr.Blocks)


def test_settings_default_to_gemini_and_can_switch():
    assert (Settings.from_env({}).provider, Settings.from_env({}).model) == (
        "gemini",
        "gemini-3.8-flash",
    )
    assert Settings.from_env({"FLIGHTAI_PROVIDER": "ollama"}).model == "llama3.2"
    assert Settings.from_env({"FLIGHTAI_MODEL": "x"}, provider="openai").model == "x"
    with pytest.raises(ValueError, match="Unknown provider"):
        Settings.from_env({"FLIGHTAI_PROVIDER": "nope"})


def test_cli_explains_a_missing_key(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "FLIGHTAI_PROVIDER"):
        monkeypatch.delenv(var, raising=False)
    assert main([]) == 2
    assert "GEMINI_API_KEY or GOOGLE_API_KEY" in capsys.readouterr().err
