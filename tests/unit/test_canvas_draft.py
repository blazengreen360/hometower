"""Unit tests for the three new draft JS modules (HT-051)."""
from src.ui.components.canvas_draft import CANVAS_DRAFT_JS
from src.ui.components.canvas_draft_form import CANVAS_DRAFT_FORM_JS
from src.ui.components.canvas_draft_publish import CANVAS_DRAFT_PUBLISH_JS


class TestCanvasDraftJS:
    """Verify CANVAS_DRAFT_JS contains expected function declarations."""

    def test_contains_isDraft(self) -> None:
        assert "_htIsDraft" in CANVAS_DRAFT_JS

    def test_contains_isDraftEdge(self) -> None:
        assert "_htIsDraftEdge" in CANVAS_DRAFT_JS

    def test_contains_draftId(self) -> None:
        assert "_htDraftId" in CANVAS_DRAFT_JS

    def test_contains_buildDraftNode(self) -> None:
        assert "_htBuildDraftNode" in CANVAS_DRAFT_JS

    def test_contains_updateDraftData(self) -> None:
        assert "_htUpdateDraftData" in CANVAS_DRAFT_JS

    def test_contains_draftCount(self) -> None:
        assert "_htDraftCount" in CANVAS_DRAFT_JS

    def test_contains_updateDraftBadge(self) -> None:
        assert "_htUpdateDraftBadge" in CANVAS_DRAFT_JS

    def test_contains_setDraftStatus(self) -> None:
        assert "window._htSetDraftStatus" in CANVAS_DRAFT_JS

    def test_defines_window_escapeHtml(self) -> None:
        assert "window._htEscapeHtml" in CANVAS_DRAFT_JS

    def test_defines_window_notify(self) -> None:
        assert "window._htNotify" in CANVAS_DRAFT_JS

    def test_draft_id_uses_window_guard(self) -> None:
        assert "window._htDraftId = window._htDraftId || function()" in CANVAS_DRAFT_JS
        assert "return 'draft-' + crypto.randomUUID();" in CANVAS_DRAFT_JS

    def test_isDraftEdge_detects_prefixed_local_edges(self) -> None:
        assert "edgeData.id.indexOf('draft-edge-') === 0" in CANVAS_DRAFT_JS

    def test_draft_badge_uses_unsaved_changes_flag_not_draft_node_count(self) -> None:
        assert "window._htHasUnsavedChanges === true" in CANVAS_DRAFT_JS
        assert "window._htDraftCount()" not in CANVAS_DRAFT_JS

    def test_draft_badge_shows_static_draft_chip_label(self) -> None:
        assert "badge.textContent = 'Draft';" in CANVAS_DRAFT_JS


class TestCanvasDraftFormJS:
    """Verify CANVAS_DRAFT_FORM_JS contains expected function declarations."""

    def test_contains_showDraftForm(self) -> None:
        assert "_htShowDraftForm" in CANVAS_DRAFT_FORM_JS

    def test_contains_name_field(self) -> None:
        assert "ht-draft-name" in CANVAS_DRAFT_FORM_JS

    def test_contains_escape_prevention(self) -> None:
        assert "Escape" in CANVAS_DRAFT_FORM_JS

    def test_contains_enter_submit(self) -> None:
        assert "Enter" in CANVAS_DRAFT_FORM_JS


class TestCanvasDraftPublishJS:
    """Verify CANVAS_DRAFT_PUBLISH_JS contains expected function declarations."""

    def test_contains_publishDraft(self) -> None:
        assert "_htPublishDraft" in CANVAS_DRAFT_PUBLISH_JS

    def test_contains_promoteConnections(self) -> None:
        assert "_htPromoteConnections" in CANVAS_DRAFT_PUBLISH_JS

    def test_posts_to_devices_endpoint(self) -> None:
        assert "/api/devices/" in CANVAS_DRAFT_PUBLISH_JS

    def test_posts_to_connections_endpoint(self) -> None:
        assert "/api/connections/" in CANVAS_DRAFT_PUBLISH_JS

    def test_verified_node_replacement_removes_then_adds(self) -> None:
        """Publish flow should remove() draft node then add() new node."""
        remove_idx = CANVAS_DRAFT_PUBLISH_JS.index("node.remove()")
        add_idx = CANVAS_DRAFT_PUBLISH_JS.index("cy.add(", remove_idx)
        assert remove_idx < add_idx, "remove() must precede cy.add()"

    def test_verified_node_replacement_asserts_element(self) -> None:
        """Publish flow must verify getElementById after add."""
        assert "cy.getElementById(newId).length !== 1" in CANVAS_DRAFT_PUBLISH_JS

    def test_verified_node_replacement_rollback(self) -> None:
        """Publish flow must rollback on verification failure."""
        assert "Node replacement verification failed" in CANVAS_DRAFT_PUBLISH_JS

    def test_no_mutable_id_via_data(self) -> None:
        """Publish must NOT mutate ID via node.data('id', ...)."""
        assert "node.data('id'," not in CANVAS_DRAFT_PUBLISH_JS

    def test_uses_window_escapeHtml(self) -> None:
        assert "window._htEscapeHtml" in CANVAS_DRAFT_PUBLISH_JS

    def test_uses_window_notify(self) -> None:
        assert "window._htNotify" in CANVAS_DRAFT_PUBLISH_JS

    def test_no_bare_escapeHtml(self) -> None:
        """Publish must not use closure-scoped _escapeHtml."""
        import re
        bare = re.findall(r'(?<!window\.)(?<!_ht)_escapeHtml', CANVAS_DRAFT_PUBLISH_JS)
        assert bare == [], f"Found bare _escapeHtml references: {bare}"

    def test_no_bare_notify(self) -> None:
        """Publish must not use closure-scoped _notify."""
        import re
        bare = re.findall(r'(?<!window\.)(?<!_ht)_notify\b', CANVAS_DRAFT_PUBLISH_JS)
        assert bare == [], f"Found bare _notify references: {bare}"

    def test_publish_failure_toast_is_persistent_and_actionable(self) -> None:
        assert "Publish failed — your draft has been kept. Try again or reload." in CANVAS_DRAFT_PUBLISH_JS
        assert "position: 'top-center'" in CANVAS_DRAFT_PUBLISH_JS
        assert "timeout: 0" in CANVAS_DRAFT_PUBLISH_JS

    def test_publish_failure_keeps_draft_error_state(self) -> None:
        assert ".addClass('draft-error');" in CANVAS_DRAFT_PUBLISH_JS
        assert "setTimeout(function() { node.removeClass('draft-error'); }, 5000);" not in CANVAS_DRAFT_PUBLISH_JS

    def test_publish_verifies_add_results_during_replace_and_rollback(self) -> None:
        assert "var addedNode = cy.add({" in CANVAS_DRAFT_PUBLISH_JS
        assert "addedNode.length !== 1" in CANVAS_DRAFT_PUBLISH_JS
        assert "var restoredNode = cy.add({" in CANVAS_DRAFT_PUBLISH_JS
        assert "if (restoredNode.length !== 1) {" in CANVAS_DRAFT_PUBLISH_JS
        assert "cy.getElementById(edgeData.id).length !== 0" in CANVAS_DRAFT_PUBLISH_JS

    def test_publish_rollback_surfaces_graph_corruption_banner(self) -> None:
        assert "window._htShowGraphCorruption();" in CANVAS_DRAFT_PUBLISH_JS
        assert "Graph may be corrupted. Please reload the page to restore from last saved state." in CANVAS_DRAFT_JS
        assert "label: 'Reload'" in CANVAS_DRAFT_JS
        assert "window.location.reload()" in CANVAS_DRAFT_JS

    def test_promote_connections_supports_prefixed_edges_and_skips_duplicates(self) -> None:
        assert "window._htIsDraftEdge(edge.data())" in CANVAS_DRAFT_PUBLISH_JS
        assert "_htHasPersistedConnection(cy, src, tgt)" in CANVAS_DRAFT_PUBLISH_JS

    def test_publish_waits_for_promotions_before_flushing_autosave(self) -> None:
        promote_chain = "return _htPromoteConnections(newId).then(function() {"
        assert promote_chain in CANVAS_DRAFT_PUBLISH_JS
        promote_idx = CANVAS_DRAFT_PUBLISH_JS.index(promote_chain)
        flush_idx = CANVAS_DRAFT_PUBLISH_JS.index("if (window._htFlushAutosave) window._htFlushAutosave();")
        notify_idx = CANVAS_DRAFT_PUBLISH_JS.index("window._htNotify('Device published to inventory.', 'positive');")
        assert promote_idx < flush_idx < notify_idx

    def test_publish_dispatches_stencil_device_published_event(self) -> None:
        assert "ht:stencil-device-published" in CANVAS_DRAFT_PUBLISH_JS
        assert "var stencilDevice = {" in CANVAS_DRAFT_PUBLISH_JS
        assert "if (window.htStencilUpsertPublishedDevice) window.htStencilUpsertPublishedDevice(stencilDevice);" in CANVAS_DRAFT_PUBLISH_JS
        assert "detail: { device: stencilDevice }" in CANVAS_DRAFT_PUBLISH_JS

    def test_promote_connections_reconciles_duplicates_after_async_settlement(self) -> None:
        assert "function _htPrunePromotedDraftEdges(cy, node)" in CANVAS_DRAFT_PUBLISH_JS
        assert "return Promise.all(promotions).then(function() {" in CANVAS_DRAFT_PUBLISH_JS
        assert "_htPrunePromotedDraftEdges(cy, node);" in CANVAS_DRAFT_PUBLISH_JS
        assert ".then(function(r) { return r.ok ? r.json() : null; })" not in CANVAS_DRAFT_PUBLISH_JS


class TestCanvasDraftFormEditableType:
    """Verify type field is editable in the draft form."""

    def test_type_field_not_disabled(self) -> None:
        assert "typeInput.disabled" not in CANVAS_DRAFT_FORM_JS

    def test_submits_type_input_value(self) -> None:
        assert "typeInput.value.trim()" in CANVAS_DRAFT_FORM_JS
