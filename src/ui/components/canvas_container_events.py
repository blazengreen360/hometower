"""Container-specific Cytoscape.js event handlers (HT-021)."""

from src.ui.components.canvas_container_unconvert import CANVAS_CONTAINER_UNCONVERT_JS


CANVAS_CONTAINER_EVENTS_JS = """
        document.addEventListener('ht:node-convert-container', function(evt) {
            var d = evt.detail;
            if (!window._cy) return;
            var node = window._cy.getElementById(d.id);
            if (node.length) {
                node.addClass('container');
                _notify('Device converted to container.', 'positive');
            }
        });

        function _htNormalizeParentId(value) {
            return value == null || value === '' ? null : String(value);
        }

        function _htClearDragOrigin(nodeId) {
            if (!window._htContainerDragOrigin) return;
            delete window._htContainerDragOrigin[nodeId];
        }

        function _htResolveDropParent(node) {
            var nodePos = node.position();
            var nodeId = node.id();
            var compounds = cy.nodes(':parent, .container').filter(function(n) {
                return n.id() !== nodeId;
            });
            var newParent = null;
            compounds.forEach(function(compound) {
                var ancestors = compound.ancestors();
                if (ancestors.filter(function(a) {
                    return a.id() === nodeId;
                }).length > 0) { return; }
                var bb = compound.boundingBox();
                if (nodePos.x >= bb.x1 && nodePos.x <= bb.x2 &&
                    nodePos.y >= bb.y1 && nodePos.y <= bb.y2) {
                    newParent = compound.id();
                }
            });
            return _htNormalizeParentId(newParent);
        }

        function _htSnapBackNode(node) {
            var origin = window._htContainerDragOrigin && window._htContainerDragOrigin[node.id()];
            if (!origin) return;
            if (_htNormalizeParentId(node.data('parent')) !== origin.parentId) {
                node.move({ parent: origin.parentId });
            }
            node.animate({
                position: {
                    x: origin.position.x,
                    y: origin.position.y
                }
            }, {
                duration: 200,
                easing: 'ease-out'
            });
            _htClearDragOrigin(node.id());
        }

        function _htFinishReparent(node, targetParent, version) {
            node.move({ parent: targetParent });
            node.data('version', Number(version || node.data('version') || 1));
            _htClearDragOrigin(node.id());
            _notify(
                targetParent
                    ? 'Device moved into container.'
                    : 'Device moved to top level.',
                'positive'
            );
        }

        function _htHandleReparentFailure(node, message) {
            _htSnapBackNode(node);
            _notify(message, 'negative');
        }

        function _htAttemptReparent(node, targetParent, knownVersion, attemptNumber) {
            var nodeId = node.id();
            fetch('/api/devices/' + nodeId, {
                method: 'PATCH',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    parent_id: targetParent || null,
                    version: Number(knownVersion || 1)
                })
            }).then(function(r) {
                if (r.ok) return r.json().then(function(updated) {
                    _htFinishReparent(node, targetParent, updated.version);
                    return null;
                });
                if (r.status !== 409) throw new Error('reparent-failed');
                if (attemptNumber >= 2) throw new Error('reparent-conflict');
                return fetch('/api/devices/' + nodeId, {
                    credentials: 'include'
                }).then(function(refreshResp) {
                    if (!refreshResp.ok) throw new Error('reparent-failed');
                    return refreshResp.json();
                }).then(function(device) {
                    var serverParent = _htNormalizeParentId(device.parent_id);
                    if (serverParent === targetParent) {
                        _htFinishReparent(node, targetParent, device.version);
                        return null;
                    }
                    return _htAttemptReparent(
                        node,
                        targetParent,
                        device.version,
                        attemptNumber + 1
                    );
                });
            }).catch(function(err) {
                if (err && err.message === 'reparent-conflict') {
                    _htHandleReparentFailure(
                        node,
                        'Reparent failed — the device was modified by another user. Your change was not saved.'
                    );
                    return;
                }
                _htHandleReparentFailure(
                    node,
                    'Reparent failed — your change was not saved.'
                );
            });
        }

        function _htStripClasses(classes) {
            if (typeof classes !== 'string') return classes;
            return classes.split(/\\s+/).filter(function(value) {
                return value && value !== 'container' && value !== 'collapsed';
            }).join(' ');
        }

        cy.on('grab', 'node', function(evt) {
            var node = evt.target;
            window._htContainerDragOrigin = window._htContainerDragOrigin || {};
            window._htContainerDragOrigin[node.id()] = {
                parentId: _htNormalizeParentId(node.data('parent')),
                position: {
                    x: node.position().x,
                    y: node.position().y
                }
            };
        });

        cy.on('dragfree', 'node', function(evt) {
            if (window.HT_READONLY) return;
            var node = evt.target;
            var nodeId = node.id();
            var origin = window._htContainerDragOrigin && window._htContainerDragOrigin[nodeId];
            var currentParent = origin
                ? origin.parentId
                : _htNormalizeParentId(node.data('parent'));
            var targetParent = _htResolveDropParent(node);

            if (targetParent === currentParent) {
                _htClearDragOrigin(nodeId);
                return;
            }

            if (window._htIsDraft && window._htIsDraft(nodeId)) {
                node.move({ parent: targetParent });
                _htClearDragOrigin(nodeId);
                if (window.scheduleAutosave) window.scheduleAutosave(800);
                return;
            }

            _htAttemptReparent(
                node,
                targetParent,
                Number(node.data('version') || 1),
                0
            );
        });

        document.addEventListener('ht:node-collapse-toggle', function(evt) {
            var d = evt.detail;
            if (!window._cy) return;
            var node = window._cy.getElementById(d.id);
            if (!node.length) { return; }

            var isCollapsed = node.data('_collapsed');
            if (isCollapsed) {
                node.children().forEach(function(child) {
                    child.style('display', 'element');
                    child.connectedEdges().style('display', 'element');
                });
                node.data('_collapsed', false);
                node.removeClass('collapsed');
            } else {
                node.children().forEach(function(child) {
                    child.style('display', 'none');
                    child.connectedEdges().forEach(function(edge) {
                        var srcParent = edge.source().data('parent');
                        var tgtParent = edge.target().data('parent');
                        // Only hide internal edges; edges crossing the boundary stay visible
                        if (srcParent === d.id && tgtParent === d.id) {
                            edge.style('display', 'none');
                        }
                    });
                });
                node.data('_collapsed', true);
                node.addClass('collapsed');
            }
            // Persist collapse state via debounced autosave (both collapse and expand)
            if (window.scheduleAutosave) window.scheduleAutosave(800);
        });
""" + CANVAS_CONTAINER_UNCONVERT_JS
