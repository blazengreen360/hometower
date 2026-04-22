"""Focused regression tests for HT-077 convert-to-container persistence."""

from src.ui.components.canvas_container_events import CANVAS_CONTAINER_EVENTS_JS


class TestCanvasConvertPersistence:
    def test_convert_to_container_flushes_autosave_from_mutation_site(self) -> None:
        marker = "document.addEventListener('ht:node-convert-container', function(evt) {"
        start = CANVAS_CONTAINER_EVENTS_JS.index(marker)
        end = CANVAS_CONTAINER_EVENTS_JS.index(
            "document.addEventListener('ht:node-collapse-toggle', function(evt) {",
            start,
        )
        convert_body = CANVAS_CONTAINER_EVENTS_JS[start:end]

        assert "window._htFlushAutosave();" in convert_body
        assert "else if (window.scheduleAutosave) window.scheduleAutosave(800);" in convert_body