"""Internal network overlay engine JS for topology canvas highlighting."""
from src.ui.components.canvas_network_overlay_badges import _NETWORK_OVERLAY_BADGES_JS

_NETWORK_OVERLAY_ENGINE_JS = """
(function() {
    if (window._htNetworkOverlayEngineLoaded) return;
    window._htNetworkOverlayEngineLoaded = true;

    var state = {
        activeNetworkIds: [],
        activeColorById: {},
        redrawFrame: null,
        eventsBound: false,
    };

    function _withCy(callback, attempt) {
        var n = attempt || 0;
        if (window._cy) {
            callback(window._cy);
            return;
        }
        if (n >= 40) return;
        setTimeout(function() { _withCy(callback, n + 1); }, 100);
    }

    function _id(value) {
        return String(value || '');
    }

    function _defaultHighlightColor() {
        var root = document.documentElement;
        var accent = window.getComputedStyle(root).getPropertyValue('--ht-accent').trim();
        return accent || 'var(--ht-accent)';
    }

    function _normalizeIds(rawIds) {
        var seen = {};
        var ids = [];
        if (!Array.isArray(rawIds)) return ids;
        rawIds.forEach(function(rawId) {
            var networkId = _id(rawId);
            if (!networkId || seen[networkId]) return;
            seen[networkId] = true;
            ids.push(networkId);
        });
        return ids;
    }

    function _activeSet() {
        var set = {};
        state.activeNetworkIds.forEach(function(networkId) {
            set[networkId] = true;
        });
        return set;
    }

    function _sanitizeMemberships(rawMemberships) {
        var memberships = [];
        if (!Array.isArray(rawMemberships)) return memberships;
        rawMemberships.forEach(function(membership) {
            if (!membership || typeof membership !== 'object') return;
            var networkId = _id(membership.network_id);
            if (!networkId) return;
            memberships.push({
                network_id: networkId,
                color: _id(membership.color),
                name: _id(membership.name),
                ip_address: _id(membership.ip_address),
            });
        });
        return memberships;
    }

    function _memberships(node) {
        return _sanitizeMemberships(node.data('network_memberships'));
    }

    function _activeMemberships(node) {
        if (state.activeNetworkIds.length === 0) return [];
        var set = _activeSet();
        return _memberships(node).filter(function(membership) {
            return !!set[membership.network_id];
        });
    }

    function _membershipColor(membership) {
        var mapped = state.activeColorById[membership.network_id];
        if (mapped) return mapped;
        return membership.color || _defaultHighlightColor();
    }

    function _clearClasses(cy) {
        cy.batch(function() {
            cy.nodes().forEach(function(node) {
                node.removeClass('ht-network-match ht-network-dim');
                node.removeData('network_highlight_color');
            });
            cy.edges().forEach(function(edge) {
                edge.removeClass('ht-network-match ht-network-dim');
            });
        });
    }
"""

_NETWORK_OVERLAY_ENGINE_JS += _NETWORK_OVERLAY_BADGES_JS

_NETWORK_OVERLAY_ENGINE_JS += """

    function _applyClasses(cy) {
        if (state.activeNetworkIds.length === 0) {
            _clearClasses(cy);
            _clearBadges();
            return;
        }

        cy.batch(function() {
            cy.nodes().forEach(function(node) {
                var activeMemberships = _activeMemberships(node);
                var isMatch = activeMemberships.length > 0;
                if (isMatch) {
                    node.data('network_highlight_color', _membershipColor(activeMemberships[0]));
                } else {
                    node.removeData('network_highlight_color');
                }
                node.toggleClass('ht-network-match', isMatch);
                node.toggleClass('ht-network-dim', !isMatch);
            });

            cy.edges().forEach(function(edge) {
                var sourceMatch = edge.source().hasClass('ht-network-match');
                var targetMatch = edge.target().hasClass('ht-network-match');
                var edgeMatch = sourceMatch && targetMatch;
                edge.toggleClass('ht-network-match', edgeMatch);
                edge.toggleClass('ht-network-dim', !edgeMatch);
            });
        });

        _renderBadges(cy);
    }

    function _scheduleApply(cy) {
        if (state.redrawFrame !== null) return;
        state.redrawFrame = window.requestAnimationFrame(function() {
            state.redrawFrame = null;
            _applyClasses(cy);
        });
    }

    function _bindEvents(cy) {
        if (state.eventsBound) return;
        state.eventsBound = true;
        ['render', 'pan', 'zoom', 'add', 'remove', 'position', 'dragfree'].forEach(function(eventName) {
            cy.on(eventName, function() {
                _scheduleApply(cy);
            });
        });
    }

    function _setActiveNetworks(networkIds, colorMap) {
        state.activeNetworkIds = _normalizeIds(networkIds);
        state.activeColorById = {};
        if (colorMap && typeof colorMap === 'object') {
            Object.keys(colorMap).forEach(function(rawId) {
                var networkId = _id(rawId);
                var color = _id(colorMap[rawId]);
                if (!networkId || !color) return;
                state.activeColorById[networkId] = color;
            });
        }
        _withCy(function(cy) {
            _bindEvents(cy);
            _scheduleApply(cy);
        }, 0);
    }

    function _refreshOverlay() {
        _withCy(function(cy) {
            _bindEvents(cy);
            _scheduleApply(cy);
        }, 0);
    }

    function _patchNodeMemberships(nodeId, memberships) {
        var targetId = _id(nodeId);
        if (!targetId) return;
        var normalized = _sanitizeMemberships(memberships);
        _withCy(function(cy) {
            var node = cy.getElementById(targetId);
            if (!node || !node.length) return;
            node.data('network_memberships', normalized);
            _bindEvents(cy);
            _scheduleApply(cy);
        }, 0);
    }

    window._htNetworkOverlay = {
        setActiveNetworks: _setActiveNetworks,
        applyNetworkFilter: function(networkId, color) {
            var id = _id(networkId);
            if (!id) {
                _setActiveNetworks([], {});
                return;
            }
            var colors = {};
            colors[id] = _id(color) || _defaultHighlightColor();
            _setActiveNetworks([id], colors);
        },
        clear: function() { _setActiveNetworks([], {}); },
        refresh: _refreshOverlay,
        getActiveNetworks: function() { return state.activeNetworkIds.slice(); },
        patchNodeMemberships: _patchNodeMemberships,
    };
})();
"""
