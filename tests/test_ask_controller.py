"""Tests for ask_controller.py — the pure Jarvis state/decision logic.

These are the model-selection, page-state, and conversation-thread decisions that
used to be scattered across MainWindow's _ask_* methods and loose self._ask_*
attributes; extracting them makes them testable without Qt or Ollama.
"""
from ask_controller import Conversation, resolve_model, page_state
from rules_agent import DEFAULT_MODEL


# ── resolve_model ────────────────────────────────────────────────────────────

def test_resolve_model_keeps_installed_preference():
    assert resolve_model("mixtral", ["llama3.1", "mixtral"]) == "mixtral"


def test_resolve_model_falls_back_when_preference_not_installed():
    # Preference isn't in the installed list -> pick a default from what's there.
    chosen = resolve_model("nonexistent", ["llama3.1", "mixtral"])
    assert chosen in ("llama3.1", "mixtral")


def test_resolve_model_blank_preference_uses_default_without_model_list():
    assert resolve_model("", None) == DEFAULT_MODEL
    assert resolve_model("   ", None) == DEFAULT_MODEL


def test_resolve_model_strips_whitespace():
    assert resolve_model("  mixtral  ", ["mixtral"]) == "mixtral"


# ── page_state ───────────────────────────────────────────────────────────────

def test_page_state_ready_only_when_ollama_up_with_models():
    assert page_state(True, ["llama3.1"]) == "ready"


def test_page_state_setup_when_down_or_no_models():
    assert page_state(False, ["llama3.1"]) == "setup"
    assert page_state(True, []) == "setup"
    assert page_state(True, None) == "setup"


# ── Conversation ─────────────────────────────────────────────────────────────

def test_conversation_starts_empty():
    c = Conversation()
    assert c.pairs == [] and c.view is None and c.question == ""


def test_conversation_begin_then_record_appends_pair():
    c = Conversation()
    sentinel_view = object()
    c.begin("how does THAC0 work?", "mixtral", ["mixtral"], sentinel_view)
    assert c.view is sentinel_view and c.model == "mixtral"

    c.record_answer("Lower is better.")
    assert c.pairs == [("how does THAC0 work?", "Lower is better.")]


def test_conversation_accumulates_multiple_turns():
    c = Conversation()
    c.begin("q1", "m", None, None); c.record_answer("a1")
    c.begin("q2", "m", None, None); c.record_answer("a2")
    assert c.pairs == [("q1", "a1"), ("q2", "a2")]


def test_conversation_reset_clears_thread():
    c = Conversation()
    c.begin("q", "m", None, None); c.record_answer("a")
    c.reset()
    assert c.pairs == []
