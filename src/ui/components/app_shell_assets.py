"""Shared assets for the authenticated app shell."""

_SESSION_EXPIRY_JS = """
(function() {
    if (window._htFetchIntercepted) return;
    window._htFetchIntercepted = true;
    var _origFetch = window.fetch;
    window.fetch = function() {
        var args = arguments;
        return _origFetch.apply(this, args).then(function(response) {
            var url = (typeof args[0] === 'string' ? args[0] : (args[0] && args[0].url)) || '';
            if (response.status === 401 && url.indexOf('/api/') !== -1) {
                _htShowExpiredOverlay();
            }
            return response;
        });
    };
    function _htShowExpiredOverlay() {
        if (document.getElementById('ht-session-expired-overlay')) return;
        var s = getComputedStyle(document.documentElement);
        var overlay = document.createElement('div');
        overlay.id = 'ht-session-expired-overlay';
        overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;'
            + 'background:color-mix(in srgb, var(--ht-bg-base) 82%, var(--ht-bg-surface));display:flex;align-items:center;'
            + 'justify-content:center;z-index:99999;';
        var box = document.createElement('div');
        box.style.cssText = 'background:' + s.getPropertyValue('--ht-bg-surface-raised').trim() + ';padding:32px;border-radius:12px;'
            + 'text-align:center;max-width:400px;border:1px solid ' + s.getPropertyValue('--ht-border').trim() + ';'
            + 'box-shadow:' + s.getPropertyValue('--ht-shadow-md').trim() + ';';
        var msg = document.createElement('p');
        msg.innerText = 'Your session has expired. Please sign in again.';
        msg.style.cssText = 'color:' + s.getPropertyValue('--ht-text-primary').trim() + ';font-size:1rem;margin-bottom:16px;';
        var btn = document.createElement('button');
        btn.innerText = 'Sign In';
        btn.style.cssText = 'background:' + s.getPropertyValue('--ht-accent').trim() + ';'
            + 'color:' + s.getPropertyValue('--ht-text-on-accent').trim() + ';border:none;'
            + 'padding:10px 24px;border-radius:6px;cursor:pointer;font-size:1rem;';
        btn.onclick = function() {
          var next = encodeURIComponent(
            (window.location.pathname || '/')
            + (window.location.search || '')
            + (window.location.hash || '')
          );
            window.location.href = '/login?expired=1&next=' + next;
        };
        box.appendChild(msg);
        box.appendChild(btn);
        overlay.appendChild(box);
        document.body.appendChild(overlay);
    }
})();
"""


_GLOBAL_CSS = """
<style id="ht-global">
  * { box-sizing: border-box; }
    html, body { min-height: 100vh; height: 100%; }
  body {
    font-family: var(--ht-font-body);
    background:
      radial-gradient(circle at top left, color-mix(in srgb, var(--ht-accent) 16%, transparent) 0, transparent 34%),
            linear-gradient(180deg, color-mix(in srgb, var(--ht-bg-base) 92%, transparent), var(--ht-bg-base));
  }
    .q-layout,
    .q-page-container,
    .q-page,
    .nicegui-content {
        min-height: 0;
        height: 100%;
    }
    .q-page-container,
    .q-page,
    .nicegui-content {
        display: flex;
        flex-direction: column;
    }
    .q-page-container {
        height: 100vh;
    }
  .nicegui-content {
    background:
      linear-gradient(180deg, transparent, color-mix(in srgb, var(--ht-bg-base) 92%, transparent)),
      radial-gradient(circle at top right, color-mix(in srgb, var(--ht-accent) 8%, transparent) 0, transparent 30%);
  }
  @keyframes htFadeIn { from { opacity: 0; } to { opacity: 1; } }
  .ht-page-content { animation: htFadeIn var(--ht-transition-fast); }
  .ht-nav-item:hover { background-color: color-mix(in srgb, var(--ht-accent) 9%, var(--ht-bg-surface-raised)); }
  .ht-sidebar-reopen {
    display: none !important;
  }
  body.ht-sidebar-collapsed .ht-sidebar-reopen {
    display: inline-flex !important;
  }
    body.ht-sidebar-collapsed #ht-app-sidebar {
        width: 0 !important;
        min-width: 0 !important;
        border-right: 0 !important;
        overflow: hidden !important;
        transform: translateX(-100%) !important;
    }
    body.ht-sidebar-collapsed .q-page-container {
        padding-left: 0 !important;
    }
  @media (max-width: 768px) {
        .ht-sidebar-reopen { display: inline-flex !important; }
  }
</style>
"""