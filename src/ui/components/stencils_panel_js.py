"""Inventory stencils panel JS bridge for drag/drop, rendering, and refresh."""

STENCIL_DRAG_JS: str = """
function htStencilCardDrag(el, deviceId, deviceName, deviceType, deviceIp, deviceVersion) {
    el.setAttribute('draggable', 'true');
    el.addEventListener('dragstart', function(e) {
        e.dataTransfer.setData('inventoryDeviceId', deviceId);
        e.dataTransfer.setData('inventoryDeviceName', deviceName);
        e.dataTransfer.setData('inventoryDeviceType', deviceType);
        e.dataTransfer.setData('inventoryDeviceIp', deviceIp || '');
        e.dataTransfer.setData('inventoryDeviceVersion', String(deviceVersion || 1));
        e.dataTransfer.effectAllowed = 'copy';
        el.style.opacity = '0.5';
    });
    el.addEventListener('dragend', function() {
        el.style.opacity = '1';
    });
}
"""

STENCIL_DROP_HANDLER_JS: str = """
        document.addEventListener('ht:stencil-drop', function(evt) {
            if (window.HT_READONLY) return;
            var d = evt.detail;
            if (!window._cy) return;
            var deviceId = String(d.deviceId || '');
            if (!deviceId) return;

            // Duplicate prevention — one device = one node per canvas
            if (window._cy.getElementById(deviceId).length > 0) {
                _notify('Device is already placed on this canvas.', 'warning');
                return;
            }

            var deviceName = String(d.deviceName || '');
            var deviceType = String(d.deviceType || '');
            var deviceIp = String(d.deviceIp || '');
            var deviceVersion = Number(d.deviceVersion || 1);
            var shape = deviceShapes[deviceType] || 'rectangle';

            window._cy.add({
                data: {
                    id: deviceId,
                    label: _escapeHtml(deviceName),
                    raw_name: deviceName,
                    version: deviceVersion,
                    shape: shape,
                    device_type: _escapeHtml(deviceType),
                    raw_device_type: deviceType,
                    status: 'Active',
                    ip: _escapeHtml(deviceIp),
                    mac: '',
                    os: '',
                    notes: ''
                },
                position: { x: d.x || 200, y: d.y || 200 }
            });

            // Trigger autosave to persist to server
            if (window.scheduleAutosave) window.scheduleAutosave(800);

            // Notify stencils panel to grey out the placed device
            document.dispatchEvent(new CustomEvent('ht:stencil-placed', {
                detail: { deviceId: deviceId }
            }));

            _notify('Device placed on canvas.', 'positive');
        });
"""
STENCIL_PANEL_JS: str = """
(function() {
    if (window._htStencilPanelLoaded) return;
    window._htStencilPanelLoaded = true;
    var _d = [], _p = new Set(), _tc = {}, _ti = {}, _c = null;
    var _s = '', _tf = '', _B = 50;

    window.htStencilInit = function(cid, devs, placed, tc, ti, tries) {
        _c = document.getElementById(cid);
        if (!_c) {
            if ((tries || 0) < 12) window.requestAnimationFrame(function() {
                window.htStencilInit(cid, devs, placed, tc, ti, (tries || 0) + 1);
            });
            return;
        }
        _d = devs || []; _p = new Set(placed || []);
        _tc = tc || {}; _ti = ti || {};
        _render();
    };

    window.htStencilFilter = function(search, tf) {
        _s = (search || '').toLowerCase(); _tf = tf || '';
        _render();
    };

    window.htStencilToggle = function() {
        var panel = document.getElementById('ht-stencils-panel');
        if (!panel) return;
        var collapsed = panel.classList.toggle('ht-stencils-collapsed');
        var btn = document.getElementById('ht-stencil-collapse-btn');
        if (btn) {
            var ic = btn.querySelector('.q-icon');
            if (ic) ic.textContent = collapsed ? 'chevron_right' : 'chevron_left';
        }
    };

    function _filtered() {
        return _d.filter(function(d) {
            if (_s && (d.name || '').toLowerCase().indexOf(_s) === -1) return false;
            if (_tf && d.type !== _tf) return false;
            return true;
        });
    }

    function _upsert(dev) {
        if (!dev || !dev.id) return;
        _d = _d.filter(function(item) { return item.id !== dev.id; }); _d.unshift(dev);
    }
    window.htStencilUpsertPublishedDevice = function(dev) {
        if (!dev) return; _upsert(dev); _p.add(String(dev.id || '')); _render();
    };

    function _render() {
        if (!_c) return;
        _c.innerHTML = '';
        var items = _filtered(), idx = 0;
        if (!items.length) {
            _c.innerHTML = '<div style="padding:8px;color:var(--ht-text-secondary);font-size:0.75rem;">No devices in inventory</div>';
            return;
        }
        var sr = _c.closest('.q-scrollarea__container');
        function batch() {
            var f = document.createDocumentFragment();
            var end = Math.min(idx + _B, items.length);
            for (var i = idx; i < end; i++) f.appendChild(_row(items[i]));
            _c.appendChild(f);
            idx = end;
            if (idx < items.length) {
                var sn = document.createElement('div');
                sn.style.height = '1px';
                _c.appendChild(sn);
                var obs = new IntersectionObserver(function(e) {
                    if (e[0].isIntersecting) { obs.disconnect(); sn.remove(); batch(); }
                }, sr ? { root: sr } : {});
                obs.observe(sn);
            }
        }
        batch();
    }

    function _row(dev) {
        var placed = _p.has(dev.id);
        var accent = _tc[dev.type] || 'var(--ht-accent)';
        var icon = _ti[dev.type] || 'devices';
        var el = document.createElement('div');
        el.id = 'stencil-' + dev.id;
        el.className = 'ht-stencil-row' + (placed ? ' ht-stencil-placed' : '');
        el.dataset.deviceId = dev.id;
        el.style.cssText = 'display:flex;align-items:center;gap:8px;padding:5px 8px;'
            + 'border-radius:var(--ht-radius-input);cursor:' + (placed ? 'default' : 'grab') + ';'
            + 'background:var(--ht-bg-surface-raised);border:1px solid var(--ht-border);'
            + 'user-select:none;margin-bottom:4px;';
        var chip = document.createElement('div');
        chip.style.cssText = 'width:24px;height:24px;border-radius:6px;display:flex;'
            + 'align-items:center;justify-content:center;flex-shrink:0;'
            + 'background:color-mix(in srgb,' + accent + ' 10%,transparent);';
        var ic = document.createElement('span');
        ic.className = 'material-icons';
        ic.style.cssText = 'color:' + accent + ';font-size:0.875rem;';
        ic.textContent = icon;
        chip.appendChild(ic); el.appendChild(chip);
        var col = document.createElement('div');
        col.style.cssText = 'display:flex;flex-direction:column;gap:0;min-width:0;flex:1;';
        var nr = document.createElement('div');
        nr.style.cssText = 'display:flex;align-items:center;gap:4px;';
        var nm = document.createElement('span');
        nm.style.cssText = 'color:var(--ht-text-primary);font-size:0.8rem;font-weight:500;'
            + 'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;';
        nm.textContent = dev.name;
        nr.appendChild(nm);
        if (placed) nr.appendChild(_badge());
        col.appendChild(nr);
        var mr = document.createElement('div');
        mr.style.cssText = 'display:flex;align-items:center;gap:4px;';
        var tp = document.createElement('span');
        tp.style.cssText = 'font-size:0.65rem;color:var(--ht-text-secondary);';
        tp.textContent = dev.type;
        mr.appendChild(tp);
        if (dev.ip) {
            var ip = document.createElement('span');
            ip.style.cssText = 'font-size:0.65rem;color:var(--ht-text-secondary);'
                + 'font-family:var(--ht-font-mono);';
            ip.textContent = dev.ip;
            mr.appendChild(ip);
        }
        col.appendChild(mr); el.appendChild(col);
        if (!placed) htStencilCardDrag(el, dev.id, dev.name, dev.type, dev.ip, dev.version);
        return el;
    }

    function _badge() {
        var b = document.createElement('span');
        b.className = 'ht-placed-badge';
        b.style.cssText = 'font-size:0.6rem;color:var(--ht-success);'
            + 'background:color-mix(in srgb,var(--ht-success) 12%,transparent);'
            + 'padding:0 6px;border-radius:9999px;font-weight:600;display:inline-block;';
        b.textContent = 'Placed';
        return b;
    }

    document.addEventListener('ht:stencil-placed', function(evt) {
        var did = evt.detail && evt.detail.deviceId ? String(evt.detail.deviceId) : '';
        if (!did) return;
        _p.add(did);
        var el = document.getElementById('stencil-' + did);
        if (!el) return;
        el.classList.add('ht-stencil-placed');
        el.removeAttribute('draggable');
        el.style.cursor = 'default';
        var textCol = el.children[1];
        var nameRow = textCol ? textCol.children[0] : null;
        if (nameRow && !nameRow.querySelector('.ht-placed-badge')) {
            nameRow.appendChild(_badge());
        }
    });

    document.addEventListener('ht:stencil-device-published', function(evt) {
        var dev = evt.detail && evt.detail.device ? evt.detail.device : null;
        window.htStencilUpsertPublishedDevice(dev);
    });

    document.addEventListener('ht:stencil-refresh', function() {
        if (!window._cy) return;
        var ids = new Set();
        window._cy.nodes().forEach(function(n) {
            var nid = n.id();
            if (nid && !nid.startsWith('draft-') && !n.data('draft')) ids.add(nid);
        });
        _p = ids;
        _render();
    });
})();
"""
