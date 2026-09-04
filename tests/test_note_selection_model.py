"""Tests for pure Quick Note selection state."""

from ui.note_selection_model import NoteSelectionModel


def test_selection_model_selects_discards_and_snapshots():
    model = NoteSelectionModel()

    model.set_selected("one", True)
    model.set_selected("two", True)
    model.set_selected("one", False)

    assert model.snapshot() == {"two"}
    assert len(model) == 1
    assert "two" in model


def test_selection_model_retains_existing_ids():
    model = NoteSelectionModel()
    model.set_selected("one", True)
    model.set_selected("two", True)

    model.retain({"two", "three"})

    assert model.selected_ids == {"two"}


def test_selection_model_clear_reports_whether_state_changed():
    model = NoteSelectionModel()

    assert model.clear() is False
    model.set_selected("one", True)
    assert model.clear() is True
    assert model.selected_ids == set()
