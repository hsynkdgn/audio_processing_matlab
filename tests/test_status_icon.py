"""Tests for ui.status_icon.StatusIcon (headless via pytest-qt)."""

from heli_noise.ui.status_icon import StatusIcon


def test_initial_state_is_idle(qtbot) -> None:
    icon = StatusIcon()
    qtbot.addWidget(icon)
    assert icon.text() == "○"
    assert icon.toolTip() == "Not run yet"


def test_set_ok(qtbot) -> None:
    icon = StatusIcon()
    qtbot.addWidget(icon)
    icon.set_ok()
    assert icon.text() == "✓"
    assert icon.toolTip() == "Completed successfully"


def test_set_error_shows_message_in_tooltip(qtbot) -> None:
    icon = StatusIcon()
    qtbot.addWidget(icon)
    icon.set_error("Notch frequency 24000 Hz is >= Nyquist")
    assert icon.text() == "✗"
    assert icon.toolTip() == "Notch frequency 24000 Hz is >= Nyquist"


def test_can_transition_between_states(qtbot) -> None:
    icon = StatusIcon()
    qtbot.addWidget(icon)
    icon.set_ok()
    icon.set_error("boom")
    assert icon.text() == "✗"
    icon.set_idle()
    assert icon.text() == "○"
