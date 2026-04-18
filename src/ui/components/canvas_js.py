"""Cytoscape.js canvas initialisation script template."""

from src.ui.components.canvas_js_interactions import CANVAS_INTERACTIONS_JS
from src.ui.components.canvas_js_resize import CANVAS_RESIZE_JS
from src.ui.components.canvas_js_utils import CANVAS_UTILS_JS_TEMPLATE

_CANVAS_CORE_JS = """
(function() {
    if (typeof initCanvas !== 'undefined') return;

    var HT_CANVAS_RETRY_DELAY_MS = 100;
    var HT_CANVAS_INIT_MAX_ATTEMPTS = 50;

    window._htSelectedCallback = null;

    function _htRetryContainerInit(elements, savedPositions, deviceShapes, currentAttempt) {
        if (currentAttempt >= HT_CANVAS_INIT_MAX_ATTEMPTS) {
            console.error('Hometower canvas init failed: #cy container not ready within 5 seconds.');
            return;
        }
        window.setTimeout(function() {
            window.initCanvas(elements, savedPositions, deviceShapes, currentAttempt + 1);
        }, HT_CANVAS_RETRY_DELAY_MS);
    }

    function _htMarkNodesPositioned(nodes) {
        nodes.forEach(function(node) {
            node.data('_positioned', true);
        });
    }

    function _htApplyCollapsedState(cy) {
        cy.nodes().forEach(function(n) {
            if (!n.data('_collapsed')) return;
            n.children().forEach(function(child) {
                child.style('display', 'none');
                child.connectedEdges().forEach(function(edge) {
                    var src = edge.source();
                    var tgt = edge.target();
                    if (src.data('parent') === n.id() && tgt.data('parent') === n.id()) {
                        edge.style('display', 'none');
                    }
                });
            });
            n.addClass('collapsed');
        });
    }

    function _htPlaceOverflowNodes(cy) {
        var unpositioned = cy.nodes().filter(function(n) {
            return n.data('_positioned') !== true;
        });
        if (unpositioned.length === 0) return 0;
        var positioned = cy.nodes().filter(function(n) {
            return n.data('_positioned') === true;
        });
        var bb = positioned.length > 0
            ? positioned.boundingBox()
            : { x1: 0, y1: 0, x2: 400, y2: 400 };
        var startX = bb.x2 + 100;
        var startY = (bb.y1 + bb.y2) / 2;
        unpositioned.forEach(function(n, i) {
            n.position({ x: startX, y: startY + (i * 80) });
            n.data('_positioned', true);
        });
        return unpositioned.length;
    }

    function _htRunFirstLoadLayout(cy, hasSavedViewport) {
        cy.layout({ name: 'cose', animate: false, fit: false }).run();
        _htMarkNodesPositioned(cy.nodes());
        if (!hasSavedViewport) cy.fit(undefined, 40);
    }

    window.htAutoLayout = function(options) {
        if (!window._cy) {
            return { ok: false, error: 'canvas-unavailable' };
        }
        if (window.HT_READONLY) {
            if (window._htNotify) {
                window._htNotify('Enter Edit mode to run Auto-Layout.', 'info');
            }
            return { ok: false, error: 'readonly' };
        }

        var cy = window._cy;
        var layoutOptions = {
            name: 'breadthfirst',
            directed: true,
            animate: true,
            animationDuration: 500,
            fit: true,
            padding: 40,
            spacingFactor: 1.1,
        };
        if (options && typeof options === 'object') {
            layoutOptions = Object.assign(layoutOptions, options);
        }

        try {
            var layout = cy.layout(layoutOptions);
            var hasCompleted = false;
            var onLayoutStop = function() {
                if (hasCompleted) return;
                hasCompleted = true;
                _htMarkNodesPositioned(cy.nodes());
                if (window._htResizeSyncFromSelection) {
                    window._htResizeSyncFromSelection();
                }
                if (window.scheduleAutosave) {
                    window.scheduleAutosave(300);
                }
            };
            if (layout && typeof layout.on === 'function') {
                layout.on('layoutstop', onLayoutStop);
            }
            layout.run();
            return { ok: true };
        } catch (error) {
            console.error('Hometower auto-layout failed:', error);
            if (window._htNotify) {
                window._htNotify('Auto-Layout failed.', 'negative');
            }
            return { ok: false, error: 'layout-failed' };
        }
    };

    window.initCanvas = function(elements, savedPositions, deviceShapes, attempt) {
        var currentAttempt = attempt || 0;

        if (typeof cytoscape === 'undefined') {
            if (currentAttempt >= HT_CANVAS_INIT_MAX_ATTEMPTS) {
                console.error('Hometower canvas init failed: Cytoscape did not load within 5 seconds.');
                return;
            }
            window.setTimeout(function() {
                window.initCanvas(elements, savedPositions, deviceShapes, currentAttempt + 1);
            }, HT_CANVAS_RETRY_DELAY_MS);
            return;
        }

        var container = document.getElementById('cy');
        if (!container || container.clientWidth === 0 || container.clientHeight === 0) {
            _htRetryContainerInit(elements, savedPositions, deviceShapes, currentAttempt);
            return;
        }

        window.requestAnimationFrame(function() {
            var frameOne = {
                width: container.clientWidth,
                height: container.clientHeight
            };
            window.requestAnimationFrame(function() {
                var frameTwo = {
                    width: container.clientWidth,
                    height: container.clientHeight
                };
                if (frameOne.width === frameTwo.width && frameOne.height === frameTwo.height && frameTwo.width > 0 && frameTwo.height > 0) {
                    var _htHasSavedNodePositions = window._htHasSavedNodePositions;
                    var _htHasSavedViewport = window._htHasSavedViewport;
                    var _htRestoreViewport = window._htRestoreViewport;
                    var hasSavedPositions = _htHasSavedNodePositions(savedPositions);
                    var hasSavedViewport = _htHasSavedViewport(savedPositions);

                    var cy = cytoscape({
                        container: container,
                        minZoom: 0.1,
                        maxZoom: 5,
                        elements: elements,
                        style: __HT_CANVAS_STYLE__,
                        layout: { name: 'preset' },
                    });

                    try {
                        if (hasSavedPositions) {
                            var placedCount = _htPlaceOverflowNodes(cy);
                            if (hasSavedViewport) {
                                _htRestoreViewport(cy, savedPositions);
                            }
                            if (placedCount > 0 && !hasSavedViewport) cy.fit(undefined, 40);
                        } else {
                            _htRunFirstLoadLayout(cy, hasSavedViewport);
                        }
                    } catch (layoutError) {
                        console.error('Hometower canvas layout init failed:', layoutError);
                        try {
                            if (hasSavedPositions) {
                                var fallbackPlacedCount = _htPlaceOverflowNodes(cy);
                                if (hasSavedViewport) {
                                    _htRestoreViewport(cy, savedPositions);
                                }
                                if (fallbackPlacedCount > 0 && !hasSavedViewport) cy.fit(undefined, 40);
                            } else {
                                cy.layout({ name: 'grid', animate: false, fit: false }).run();
                                _htMarkNodesPositioned(cy.nodes());
                                if (hasSavedViewport) {
                                    _htRestoreViewport(cy, savedPositions);
                                } else {
                                    cy.fit(undefined, 40);
                                }
                            }
                        } catch (fallbackError) {
                            console.error('Hometower canvas fallback init failed:', fallbackError);
                        }
                    }

                    try {
                        _htApplyCollapsedState(cy);
                    } catch (collapsedError) {
                        console.error('Hometower canvas collapsed-state recovery failed:', collapsedError);
                    }

                    window._cy = cy;

                    // Default to view-only interaction state for all users
                    // Note: autounselectify is intentionally NOT set here — it globally locks
                    // selectability and prevents Ctrl+A / Escape shortcuts from working.
                    cy.autoungrabify(true);
                    cy.boxSelectionEnabled(false);
                    if (window._htResizeSetEnabled) window._htResizeSetEnabled(false);

                    cy.on('add', 'node', function(evt) {
                        evt.target.data('_positioned', true);
                    });
                    cy.on('dragfree', 'node', function(evt) {
                        evt.target.data('_positioned', true);
                    });

                    // Store deviceShapes for deferred wiring when entering edit mode
                    window._htDeviceShapes = deviceShapes || {};

                    window._htBindCanvasInteractions(cy, container);
                    if (window._htBindCanvasResize) window._htBindCanvasResize(cy, container);
                    window._htPersistPrunedLayoutCleanup(savedPositions);
                    return;
                }
                _htRetryContainerInit(elements, savedPositions, deviceShapes, currentAttempt);
            });
        });
    };
})();
"""

CANVAS_INIT_JS_TEMPLATE = _CANVAS_CORE_JS + CANVAS_INTERACTIONS_JS + CANVAS_RESIZE_JS + CANVAS_UTILS_JS_TEMPLATE
