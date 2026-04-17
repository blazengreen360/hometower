"""Topology in-app leave guard for unsaved personal drafts (HT-074)."""
from nicegui import ui

_EDIT_ROLES = {"Admin", "Contributor"}

TOPOLOGY_LEAVE_GUARD_JS = """
(function(){
  if(window._htLeaveGuardInit) return; window._htLeaveGuardInit = true;
  window._htLeaveGuardBypassOnce = false;
  var HISTORY_BACK_TOKEN = '__ht-history-back__', BACK_BASE_KEY = '__htLeaveGuardBase', BACK_SENTINEL_KEY = '__htLeaveGuardSentinel';
  var state = { pendingUrl: null, modal: null, saveBtn: null, discardBtn: null, cancelBtn: null, busy: false, pointerTargetUrl: null }, ELEMENT_NODE = 1, TEXT_NODE = 3;
  function notify(message, color){ if(window._htNotify){ window._htNotify(message, color || 'warning'); return; } window.alert(message); }
  function hasUnsaved(){ return window._htHasUnsavedChanges === true; }
  function setBusy(busy){ state.busy = !!busy; if(state.saveBtn) state.saveBtn.disabled = state.busy; if(state.discardBtn) state.discardBtn.disabled = state.busy; if(state.cancelBtn) state.cancelBtn.disabled = state.busy; }
  function markSaved(){ if(window._htSetDraftStatus){ window._htSetDraftStatus(false); return; } window._htHasUnsavedChanges = false; if(window._htUpdateDraftBadge) window._htUpdateDraftBadge(); }
  function armBypass(){ window._htLeaveGuardBypassOnce = true; window.setTimeout(function(){ window._htLeaveGuardBypassOnce = false; }, 1500); }
  function closeModal(){ if(!state.modal) return; state.modal.style.display = 'none'; setBusy(false); state.pendingUrl = null; }
  function ensureBackNavigationTrap(){
    if(!window.history || !window.history.pushState || !window.history.replaceState) return;
    try {
      var currentState = window.history.state;
      if(currentState && typeof currentState === 'object' && currentState[BACK_SENTINEL_KEY] === true) return;
      if(currentState && typeof currentState === 'object' && currentState[BACK_BASE_KEY] === true){ var existingSentinel = {}; existingSentinel[BACK_SENTINEL_KEY] = true; window.history.pushState(existingSentinel, '', window.location.href); return; }
      var baseState = {};
      if(currentState && typeof currentState === 'object'){
        for(var key in currentState){ if(Object.prototype.hasOwnProperty.call(currentState, key)) baseState[key] = currentState[key]; }
      }
      baseState[BACK_BASE_KEY] = true;
      window.history.replaceState(baseState, '', window.location.href);
      var sentinelState = {}; sentinelState[BACK_SENTINEL_KEY] = true;
      window.history.pushState(sentinelState, '', window.location.href);
    } catch(_err) {}
  }
  function proceed(targetUrl){
    if(!targetUrl) return;
    armBypass();
    if(targetUrl === HISTORY_BACK_TOKEN){
      if(window.history && window.history.length > 2 && window.history.go){ window.history.go(-2); return; }
      if(window.history && window.history.length > 1 && window.history.back){ window.history.back(); return; }
      window._htLeaveGuardBypassOnce = false;
      return;
    }
    window.location.assign(targetUrl);
  }
  function ensureModal(){
    if(state.modal) return;
    var root = document.createElement('div'); var card = document.createElement('div'); var title = document.createElement('h3');
    var body = document.createElement('p'); var actions = document.createElement('div'); var cancelBtn = document.createElement('button');
    var discardBtn = document.createElement('button'); var saveBtn = document.createElement('button');
    root.id = 'ht-leave-guard-modal';
    root.style.cssText = 'position:fixed;inset:0;display:none;align-items:center;justify-content:center;z-index:100001;background:rgba(15,23,42,0.55);';
    card.style.cssText = 'width:min(540px,92vw);background:var(--ht-bg-surface,#111827);color:var(--ht-text-primary,#f8fafc);border:1px solid var(--ht-border,#334155);border-radius:12px;padding:18px 18px 16px;box-shadow:0 18px 40px rgba(2,6,23,0.45);';
    title.textContent = 'You have unsaved topology changes'; title.style.cssText = 'margin:0 0 8px;font-size:1.05rem;';
    body.textContent = 'Choose how to continue before leaving this topology.';
    body.style.cssText = 'margin:0 0 14px;color:var(--ht-text-secondary,#94a3b8);font-size:0.92rem;';
    actions.style.cssText = 'display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap;';
    cancelBtn.textContent = 'Cancel'; cancelBtn.type = 'button';
    cancelBtn.style.cssText = 'padding:8px 12px;border:1px solid var(--ht-border,#334155);border-radius:8px;cursor:pointer;font-weight:600;background:transparent;color:var(--ht-text-primary,#f8fafc);';
    discardBtn.textContent = 'Discard'; discardBtn.type = 'button';
    discardBtn.style.cssText = 'padding:8px 12px;border:1px solid color-mix(in srgb,var(--ht-error,#ef4444) 65%,#000 0%);border-radius:8px;cursor:pointer;font-weight:600;background:color-mix(in srgb,var(--ht-error,#ef4444) 15%,transparent);color:var(--ht-error,#ef4444);';
    saveBtn.textContent = 'Save Version'; saveBtn.type = 'button';
    saveBtn.style.cssText = 'padding:8px 12px;border:none;border-radius:8px;cursor:pointer;font-weight:600;background:var(--ht-accent,#22c55e);color:var(--ht-text-on-accent,#052e16);';
    actions.appendChild(cancelBtn); actions.appendChild(discardBtn); actions.appendChild(saveBtn);
    card.appendChild(title); card.appendChild(body); card.appendChild(actions); root.appendChild(card); document.body.appendChild(root);
    state.modal = root; state.saveBtn = saveBtn; state.discardBtn = discardBtn; state.cancelBtn = cancelBtn;
    cancelBtn.addEventListener('click', function(){ closeModal(); });
    saveBtn.addEventListener('click', function(){ saveVersionThenNavigate(); });
    discardBtn.addEventListener('click', function(){ discardDraftThenNavigate(); });
  }
  function openModal(targetUrl){ ensureModal(); state.pendingUrl = targetUrl; state.modal.style.display = 'flex'; setBusy(false); }
  async function saveVersionThenNavigate(){
    if(state.busy || !state.pendingUrl) return;
    if(!window._htTopologyId){ notify('Cannot save before leaving: missing topology context.', 'negative'); return; }
    setBusy(true);
    try {
      var payload = { base_diagram_version: window._htDiagramVersion || null };
      if(window.getCanvasJson) payload.cytoscape_json = window.getCanvasJson();
      var response = await fetch('/api/topologies/' + window._htTopologyId + '/save-version', { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      if(!response.ok){ if(response.status === 409) notify('Save conflict detected. Reload to sync before leaving.', 'warning'); else notify('Save failed. Please try again before leaving.', 'negative'); return; }
      var data = await response.json();
      window._htCurrentDiagramId = data.current_diagram_id || window._htCurrentDiagramId || null;
      window._htDiagramId = window._htCurrentDiagramId;
      window._htDiagramVersion = data.current_diagram_version || window._htDiagramVersion || null;
      window._htDraftVersion = data.draft_version || null;
      markSaved();
      var targetUrl = state.pendingUrl;
      closeModal();
      proceed(targetUrl);
    } catch(_err) { notify('Save failed. Please try again before leaving.', 'negative'); }
    finally { setBusy(false); }
  }
  async function discardDraftThenNavigate(){
    if(state.busy || !state.pendingUrl) return;
    if(!window._htTopologyId){ notify('Cannot discard before leaving: missing topology context.', 'negative'); return; }
    setBusy(true);
    try {
      var response = await fetch('/api/topologies/' + window._htTopologyId + '/personal-draft', { method: 'DELETE', credentials: 'include' });
      if(!response.ok && response.status !== 404){ notify('Discard failed. Please try again before leaving.', 'negative'); return; }
      window._htDraftVersion = null;
      markSaved();
      var targetUrl = state.pendingUrl;
      closeModal();
      proceed(targetUrl);
    } catch(_err) { notify('Discard failed. Please try again before leaving.', 'negative'); }
    finally { setBusy(false); }
  }
  window.htNavigateWithGuard = function(targetUrl){ if(!targetUrl) return; if (!window._htHasUnsavedChanges) { proceed(targetUrl); return; } openModal(targetUrl); };
  function consumeNavEvent(event){ event.preventDefault(); event.stopPropagation(); if(event.stopImmediatePropagation) event.stopImmediatePropagation(); }
  function getEventTargetElement(event){
    if(!event) return null;
    var rawTarget = event.target || null;
    if(rawTarget && rawTarget.nodeType === ELEMENT_NODE) return rawTarget;
    if(rawTarget && rawTarget.nodeType === TEXT_NODE && rawTarget.parentElement) return rawTarget.parentElement;
    if(typeof event.composedPath === 'function'){
      var path = event.composedPath();
      for(var i = 0; i < path.length; i += 1){
        var node = path[i];
        if(node && node.nodeType === ELEMENT_NODE) return node;
        if(node && node.nodeType === TEXT_NODE && node.parentElement) return node.parentElement;
      }
    }
    return null;
  }
  function getGuardNavigationUrl(event, targetElement){
    var sawGuardMarkerWithoutTarget = false;
    function readGuardTarget(element){
      if(!element || !element.getAttribute) return null;
      var hasGuardMarker = element.hasAttribute('data-ht-guard-nav');
      var hasNavTarget = element.hasAttribute('data-ht-nav-target');
      if(!hasGuardMarker && !hasNavTarget) return null;
      if(element.getAttribute('aria-disabled') === 'true') return '';
      var navDisabled = element.getAttribute('data-ht-nav-disabled');
      if(navDisabled === 'true' || navDisabled === '1') return '';
      return element.getAttribute('data-ht-nav-target') || '';
    }
    function consider(element){ var resolved = readGuardTarget(element); if(resolved === '') sawGuardMarkerWithoutTarget = true; return resolved; }
    var nearest = targetElement && targetElement.closest ? targetElement.closest('[data-ht-nav-target],[data-ht-guard-nav]') : null;
    var nearestUrl = consider(nearest);
    if(nearestUrl) return nearestUrl;
    if(typeof event.composedPath === 'function'){
      var path = event.composedPath();
      for(var i = 0; i < path.length; i += 1){
        var pathNode = path[i];
        if(!pathNode || pathNode.nodeType !== ELEMENT_NODE) continue;
        var directUrl = consider(pathNode);
        if(directUrl) return directUrl;
        if(pathNode.closest){ var ancestor = pathNode.closest('[data-ht-nav-target],[data-ht-guard-nav]'); var ancestorUrl = consider(ancestor); if(ancestorUrl) return ancestorUrl; }
      }
    }
    return sawGuardMarkerWithoutTarget ? '' : null;
  }
  function handleGuardPointerDown(event){
    if(window._htLeaveGuardBypassOnce) return;
    if(typeof event.button === 'number' && event.button !== 0) return;
    if(event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    var targetElement = getEventTargetElement(event);
    var pointerTargetUrl = getGuardNavigationUrl(event, targetElement);
    if(pointerTargetUrl === null) return;
    consumeNavEvent(event);
    state.pointerTargetUrl = pointerTargetUrl || null;
    if(!pointerTargetUrl) return;
    window.htNavigateWithGuard(pointerTargetUrl);
  }
  window.addEventListener('pointerdown', handleGuardPointerDown, true);
  if(typeof window.PointerEvent === 'undefined'){ window.addEventListener('mousedown', handleGuardPointerDown, true); window.addEventListener('touchstart', handleGuardPointerDown, true); }
  window.addEventListener('click', function(event){
    if(window._htLeaveGuardBypassOnce) return;
    if(typeof event.button === 'number' && event.button !== 0) return;
    if(event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if(state.pointerTargetUrl){ consumeNavEvent(event); state.pointerTargetUrl = null; return; }
    var targetElement = getEventTargetElement(event);
    var markedUrl = getGuardNavigationUrl(event, targetElement);
    if(markedUrl !== null){ consumeNavEvent(event); if(!markedUrl) return; window.htNavigateWithGuard(markedUrl); return; }
    var link = targetElement && targetElement.closest ? targetElement.closest('a[href]') : null;
    if(!link || link.target === '_blank' || link.hasAttribute('download')) return;
    var href = link.getAttribute('href');
    if(!href || href.indexOf('#') === 0) return;
    var targetUrl;
    try { targetUrl = new URL(href, window.location.origin).toString(); }
    catch(_err) { return; }
    if(!hasUnsaved()) return;
    consumeNavEvent(event);
    window.htNavigateWithGuard(targetUrl);
  }, true);
  window.addEventListener('popstate', function(event){
    if(window._htLeaveGuardBypassOnce) return;
    var historyState = event && event.state && typeof event.state === 'object' ? event.state : null;
    if(!historyState || historyState[BACK_BASE_KEY] !== true) return;
    if(!hasUnsaved()){ armBypass(); window.history.back(); return; }
    ensureBackNavigationTrap();
    openModal(HISTORY_BACK_TOKEN);
  });
  window.addEventListener('beforeunload', function(event){
    if(window._htLeaveGuardBypassOnce || !hasUnsaved()) return;
    event.preventDefault();
    event.returnValue = 'You have unsaved topology changes.';
    return event.returnValue;
  });
  ensureBackNavigationTrap();
})();
"""


def inject_topology_leave_guard(user_role: str) -> None:
    """Inject topology leave guard script for editor-capable roles only."""
    if user_role not in _EDIT_ROLES:
        return
    ui.add_body_html(f"<script>{TOPOLOGY_LEAVE_GUARD_JS}</script>")
