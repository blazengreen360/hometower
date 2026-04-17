"""Unconvert helpers for container nodes on the Cytoscape canvas."""

CANVAS_CONTAINER_UNCONVERT_JS = """
        function _htBuildUnconvertPlan(nodeId) {
            if (!window._cy || !window.getCanvasJson) return null;
            var node = window._cy.getElementById(nodeId);
            if (!node.length) return null;
            var directChildren = node.children();
            var descendants = node.descendants();
            var removedIds = {};
            descendants.forEach(function(desc) {
                removedIds[desc.id()] = true;
            });
            var candidateJson = window.getCanvasJson();
            if (!candidateJson) return null;
            candidateJson = JSON.parse(JSON.stringify(candidateJson));
            var rawElements = candidateJson.elements;
            if (Array.isArray(rawElements)) {
                candidateJson.elements = rawElements.reduce(function(result, elem) {
                    if (!elem || typeof elem !== 'object') return result;
                    var data = elem.data || {};
                    var elemId = data && data.id ? String(data.id) : '';
                    var isEdge = elem.group === 'edges' || (data.source != null && data.target != null);
                    if (isEdge) {
                        var sourceId = data && data.source ? String(data.source) : '';
                        var targetId = data && data.target ? String(data.target) : '';
                        if (!removedIds[sourceId] && !removedIds[targetId]) result.push(elem);
                        return result;
                    }
                    if (removedIds[elemId]) return result;
                    if (elemId === nodeId) {
                        if (elem.data) {
                            delete elem.data.container;
                            delete elem.data.collapsed;
                            delete elem.data._collapsed;
                        }
                        elem.classes = _htStripClasses(elem.classes);
                    }
                    result.push(elem);
                    return result;
                }, []);
            } else if (rawElements && typeof rawElements === 'object') {
                rawElements.nodes = Array.isArray(rawElements.nodes)
                    ? rawElements.nodes.filter(function(elem) {
                        var data = elem && elem.data ? elem.data : {};
                        var elemId = data && data.id ? String(data.id) : '';
                        return !removedIds[elemId];
                    }).map(function(elem) {
                        var data = elem && elem.data ? elem.data : null;
                        if (data && String(data.id || '') === nodeId) {
                            delete data.container;
                            delete data.collapsed;
                            delete data._collapsed;
                            elem.classes = _htStripClasses(elem.classes);
                        }
                        return elem;
                    })
                    : [];
                rawElements.edges = Array.isArray(rawElements.edges)
                    ? rawElements.edges.filter(function(elem) {
                        var data = elem && elem.data ? elem.data : {};
                        var sourceId = data && data.source ? String(data.source) : '';
                        var targetId = data && data.target ? String(data.target) : '';
                        return !removedIds[sourceId] && !removedIds[targetId];
                    })
                    : [];
            }
            candidateJson.collapsedNodes = Array.isArray(candidateJson.collapsedNodes)
                ? candidateJson.collapsedNodes.filter(function(id) {
                    return String(id) !== nodeId;
                })
                : [];

            var directChildNames = [];
            directChildren.forEach(function(child) {
                if (directChildNames.length >= 5) return;
                directChildNames.push(String(child.data('raw_name') || child.data('label') || child.id()));
            });

            return {
                nodeId: nodeId,
                candidateJson: candidateJson,
                directChildNames: directChildNames,
                extraDirectChildren: Math.max(directChildren.length - directChildNames.length, 0),
                nestedDescendantCount: Math.max(descendants.length - directChildren.length, 0),
                affectedEdgeCount: descendants.connectedEdges().length
            };
        }

        function _htBuildUnconvertMessage(plan) {
            var lines = [
                '<div>Devices stay in inventory. This removes them from this topology version.</div>'
            ];
            if (plan.directChildNames.length) {
                lines.push('<div style="margin-top:8px;">' + plan.directChildNames.map(function(name) {
                    return '&bull; ' + _escapeHtml(name);
                }).join('<br>') + '</div>');
            }
            if (plan.extraDirectChildren > 0) {
                lines.push('<div style="margin-top:8px;">+' + plan.extraDirectChildren + ' more direct children</div>');
            }
            if (plan.nestedDescendantCount > 0) {
                lines.push('<div style="margin-top:8px;">Includes ' + plan.nestedDescendantCount + ' nested descendants under those children.</div>');
            }
            lines.push('<div style="margin-top:8px;">' + plan.affectedEdgeCount + ' connections will be removed from this topology version.</div>');
            return lines.join('');
        }

        function _htShowUnconvertDialog(plan, onConfirm) {
            var firstLine = 'Devices stay in inventory. This removes them from this topology version.';
            if (window.Quasar && window.Quasar.Dialog && window.Quasar.Dialog.create) {
                window.Quasar.Dialog.create({
                    title: 'Convert container to node?',
                    message: _htBuildUnconvertMessage(plan),
                    html: true,
                    ok: { label: 'Remove from Version', color: 'warning' },
                    cancel: { label: 'Cancel', flat: true, color: 'grey-6' },
                    focus: 'cancel',
                    persistent: true
                }).onOk(onConfirm);
                return;
            }
            var fallbackLines = [firstLine];
            plan.directChildNames.forEach(function(name) {
                fallbackLines.push('- ' + name);
            });
            if (plan.extraDirectChildren > 0) {
                fallbackLines.push('+' + plan.extraDirectChildren + ' more direct children');
            }
            if (plan.nestedDescendantCount > 0) {
                fallbackLines.push('Includes ' + plan.nestedDescendantCount + ' nested descendants under those children.');
            }
            fallbackLines.push(plan.affectedEdgeCount + ' connections will be removed from this topology version.');
            if (window.confirm(fallbackLines.join('\\n'))) onConfirm();
        }

        function _htApplyUnconvertPlan(plan) {
            if (!window._cy) return;
            var node = window._cy.getElementById(plan.nodeId);
            if (!node.length) return;
            node.descendants().connectedEdges().remove();
            node.descendants().remove();
            node.removeClass('container');
            node.removeClass('collapsed');
            node.removeData('container');
            node.removeData('collapsed');
            node.removeData('_collapsed');
        }

        document.addEventListener('ht:node-unconvert-container', function(evt) {
            var plan = _htBuildUnconvertPlan(evt.detail.id);
            if (!plan) return;

            _htShowUnconvertDialog(plan, function() {
                if (!window._htTopologyId) {
                    _notify('Open a topology before converting containers.', 'warning');
                    return;
                }
                if (window._htAutosaveInFlight || window._htAutosaveRequestInFlight) {
                    _notify('Save in progress — wait a moment and try again.', 'warning');
                    return;
                }
                if (window.cancelAutosave) window.cancelAutosave();

                fetch('/api/topologies/' + window._htTopologyId + '/personal-draft', {
                    method: 'PUT',
                    credentials: 'include',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        cytoscape_json: plan.candidateJson,
                        base_version: window._htDraftVersion != null ? window._htDraftVersion : null
                    })
                }).then(function(r) {
                    if (!r.ok) throw new Error('unconvert-failed');
                    return r.json();
                }).then(function(layout) {
                    window._htDraftVersion = layout.version;
                    _htApplyUnconvertPlan(plan);
                    document.dispatchEvent(new CustomEvent('ht:stencil-refresh'));
                    _notify('Container converted to node.', 'positive');
                }).catch(function() {
                    _notify('Convert to node failed — this topology version was not changed.', 'negative');
                });
            });
        });
"""