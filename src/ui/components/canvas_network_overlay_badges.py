"""Badge-rendering JS segment for canvas network overlay."""

_NETWORK_OVERLAY_BADGES_JS = """
    function _clearBadges() {
        var layer = document.getElementById('ht-network-badges');
        if (layer) layer.innerHTML = '';
    }

    function _renderBadges(cy) {
        var layer = document.getElementById('ht-network-badges');
        if (!layer) return;
        layer.innerHTML = '';
        if (state.activeNetworkIds.length === 0) return;

        cy.nodes().forEach(function(node) {
            if (typeof node.isParent === 'function' && node.isParent()) return;
            if (typeof node.visible === 'function' && !node.visible()) return;

            var activeMemberships = _activeMemberships(node);
            if (activeMemberships.length === 0) return;

            var colorSeen = {};
            var uniqueColors = [];
            activeMemberships.forEach(function(membership) {
                var color = _membershipColor(membership);
                if (!color || colorSeen[color]) return;
                colorSeen[color] = true;
                uniqueColors.push(color);
            });
            if (uniqueColors.length === 0) return;

            var pos = node.renderedPosition();
            var x = pos.x + (node.renderedWidth() / 2) - 7;
            var y = pos.y + (node.renderedHeight() / 2) - 7;

            var stack = document.createElement('div');
            stack.className = 'ht-network-badge-stack';
            stack.style.position = 'absolute';
            stack.style.left = x + 'px';
            stack.style.top = y + 'px';
            stack.style.display = 'flex';
            stack.style.alignItems = 'center';
            stack.style.pointerEvents = 'none';

            var maxDots = 4;
            uniqueColors.slice(0, maxDots).forEach(function(color, index) {
                var dot = document.createElement('span');
                dot.className = 'ht-network-badge-dot';
                dot.style.width = '10px';
                dot.style.height = '10px';
                dot.style.borderRadius = '9999px';
                dot.style.border = '1px solid color-mix(in srgb, var(--ht-bg-base) 24%, transparent)';
                dot.style.boxShadow = '0 0 0 1px color-mix(in srgb, var(--ht-bg-surface-raised) 45%, transparent)';
                dot.style.background = color;
                dot.style.marginLeft = index === 0 ? '0' : '-3px';
                stack.appendChild(dot);
            });

            if (uniqueColors.length > maxDots) {
                var overflow = document.createElement('span');
                overflow.className = 'ht-network-badge-overflow';
                overflow.textContent = '+' + String(uniqueColors.length - maxDots);
                overflow.style.fontSize = '9px';
                overflow.style.lineHeight = '1';
                overflow.style.marginLeft = '4px';
                overflow.style.padding = '1px 4px';
                overflow.style.borderRadius = '9999px';
                overflow.style.background = 'color-mix(in srgb, var(--ht-bg-base) 82%, var(--ht-bg-surface-raised))';
                overflow.style.color = 'var(--ht-text-on-accent)';
                stack.appendChild(overflow);
            }

            layer.appendChild(stack);
        });
    }
"""
