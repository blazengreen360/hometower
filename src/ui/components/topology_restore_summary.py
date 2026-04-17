"""Restore summary banner for topology ghost placeholders (HT-075)."""

import json

from nicegui import ui

_RESTORE_SUMMARY_BANNER_JS = """
(function() {
	if (window._htRestoreSummaryBannerInit) return;
	window._htRestoreSummaryBannerInit = true;

	function _bannerEl() {
		return document.getElementById('ht-restore-summary-banner');
	}

	function _toSummary(value) {
		if (!value || typeof value !== 'object') return null;
		return value;
	}

	function _setBanner(summary) {
		var el = _bannerEl();
		if (!el) return;
		var s = _toSummary(summary);
		var ghostCount = Number(s && s.ghost_count ? s.ghost_count : 0);
		if (!s || ghostCount <= 0) {
			el.textContent = '';
			el.style.display = 'none';
			return;
		}

		var message = String(
			s.message ||
			'Deleted devices were preserved as ghost placeholders instead of recreated into inventory.'
		);
		var recovery = (s.ghost_recovery && typeof s.ghost_recovery === 'object') ? s.ghost_recovery : null;
		var actionHint = recovery && recovery.can_reconcile
			? ' Select a ghost to reconcile it.'
			: ' Ghosts remain visible in read-only mode.';
		var noun = ghostCount === 1 ? 'device' : 'devices';
		var placeholders = ghostCount === 1 ? 'placeholder' : 'placeholders';

		el.textContent = ghostCount + ' deleted ' + noun + ' kept as ghost ' + placeholders + '. '
			+ message + actionHint;
		el.style.display = 'block';
	}

	window._htUpdateRestoreSummaryBanner = function(summary) {
		window._htRestoreSummary = summary || null;
		_setBanner(window._htRestoreSummary);
	};

	document.addEventListener('ht:restore-summary-updated', function(evt) {
		var detail = evt && evt.detail && typeof evt.detail === 'object' ? evt.detail : {};
		window._htUpdateRestoreSummaryBanner(detail.restore_summary || null);
	});
})();
"""


def render_restore_summary_banner(initial_summary: dict[str, object] | None) -> None:
	"""Render and initialize the persistent topology restore summary banner."""
	ui.add_body_html(f"<script>{_RESTORE_SUMMARY_BANNER_JS}</script>")

	ui.element("div").props(
		'id="ht-restore-summary-banner" role="status" aria-live="polite"'
	).style(
		"display:none; width:100%; margin:0 0 8px 0; padding:10px 12px;"
		" border-radius:var(--ht-radius-input);"
		" border:1px solid color-mix(in srgb,var(--ht-warning) 55%,var(--ht-border));"
		" background:color-mix(in srgb,var(--ht-warning) 16%,transparent);"
		" color:var(--ht-text-primary); font-size:0.875rem;"
	)

	initial_json = json.dumps(initial_summary)
	ui.run_javascript(
		"if(window._htUpdateRestoreSummaryBanner){"
		f"window._htUpdateRestoreSummaryBanner({initial_json});"
		"}"
	)
