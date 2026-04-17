"""Leaflet map bridge component for the /map page (HT-008).

Injects Leaflet + marker-cluster assets and exposes a JS bootstrap helper that
renders markers and emits marker-selection events back to NiceGUI.
"""

from nicegui import ui

_LEAFLET_CSS = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css"
_LEAFLET_JS = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"
_CLUSTER_CSS = "https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/MarkerCluster.css"
_CLUSTER_DEFAULT_CSS = "https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/MarkerCluster.Default.css"
_CLUSTER_JS = "https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/leaflet.markercluster.js"

_OSM_LIGHT_TILE = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
_OSM_LIGHT_ATTRIBUTION = (
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
)
_OSM_DARK_TILE = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
_OSM_DARK_ATTRIBUTION = (
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors '
    '&copy; <a href="https://carto.com/attributions">CARTO</a>'
)

_MAP_STYLE = """
<style id="ht-map-style">
  #ht-map-canvas {
    background: var(--ht-bg-base);
  }
  #ht-map-canvas .leaflet-tile,
  #ht-map-canvas .leaflet-marker-icon,
  #ht-map-canvas .leaflet-marker-shadow {
    max-width: none !important;
  }
  .leaflet-container {
    background: var(--ht-bg-base);
    color: var(--ht-text-primary);
  }
  .leaflet-control-zoom a {
    background: var(--ht-bg-surface-raised) !important;
    color: var(--ht-text-primary) !important;
    border-color: var(--ht-border) !important;
  }
  .leaflet-control-attribution {
    background: var(--ht-bg-surface-raised) !important;
    color: var(--ht-text-secondary) !important;
    border: 1px solid var(--ht-border);
    border-radius: 6px;
    margin: 0 10px 10px 0 !important;
    padding: 4px 8px !important;
  }
  .leaflet-control-attribution a {
    color: var(--ht-accent) !important;
  }
  .marker-cluster-small,
  .marker-cluster-medium,
  .marker-cluster-large {
    background: var(--ht-accent-glow) !important;
  }
  .marker-cluster-small div,
  .marker-cluster-medium div,
  .marker-cluster-large div {
    background: var(--ht-accent) !important;
    color: var(--ht-text-on-accent) !important;
    font-weight: 700;
  }
  #ht-map-drawer {
    transform: translateX(100%);
    transition: transform var(--ht-transition-norm);
  }
  #ht-map-drawer.ht-map-drawer-open {
    transform: translateX(0);
  }
</style>
"""

_MAP_BRIDGE_JS = """
(function() {
  if (window._htMapBridgeReady) return;
  window._htMapBridgeReady = true;

  function _toNumber(v) {
    return (typeof v === 'number' && Number.isFinite(v)) ? v : NaN;
  }

  function _deviceLabel(count) {
    return count === 1 ? 'device' : 'devices';
  }

  function _buildTooltipNode(name, count) {
    var tooltipText = document.createElement('span');
    // Use textContent so location names are treated as plain text, never HTML.
    tooltipText.textContent = name + ' \u2022 ' + count + ' ' + _deviceLabel(count);
    return tooltipText;
  }

  function _invalidateMapAfterLayout(map, host) {
    var attempts = 0;
    function attempt() {
      map.invalidateSize();
      attempts += 1;
      var rect = host.getBoundingClientRect();
      if ((rect.width <= 0 || rect.height <= 0) && attempts < 8) {
        setTimeout(attempt, 50);
      }
    }
    setTimeout(attempt, 0);
  }

  window.htRenderMap = function(config) {
    try {
      if (!window.L || typeof window.L.map !== 'function') {
        return { ok: false, error: 'leaflet-unavailable' };
      }
      if (typeof window.L.markerClusterGroup !== 'function') {
        return { ok: false, error: 'cluster-plugin-unavailable' };
      }

      var hostId = (config && config.element_id) || 'ht-map-canvas';
      var host = document.getElementById(hostId);
      if (!host) {
        return { ok: false, error: 'container-missing' };
      }

      if (window._htMapInstance) {
        window._htMapInstance.remove();
        window._htMapInstance = null;
      }

      var map = window.L.map(host, { zoomControl: true, keyboard: true });
      window._htMapInstance = map;

      var tileUrl = config && config.tile_url;
      var attribution = (config && config.attribution) || '';
      window.L.tileLayer(tileUrl, { attribution: attribution, maxZoom: 19 }).addTo(map);

      var markerGroup = window.L.markerClusterGroup({
        showCoverageOnHover: false,
        spiderfyOnMaxZoom: true,
        maxClusterRadius: 48,
      });

      var points = [];
      var markerById = {};
      var locations = Array.isArray(config && config.locations) ? config.locations : [];

      locations.forEach(function(location) {
        var lat = _toNumber(location && location.lat);
        var lng = _toNumber(location && location.lng);
        if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;

        var locationId = String(location.id || '');
        var name = String(location.name || 'Unnamed location');
        var count = Number(location.device_count || 0);
        var marker = window.L.marker([lat, lng], {
          title: name,
          keyboard: true,
          riseOnHover: true,
        });

        marker.bindTooltip(_buildTooltipNode(name, count), {
          direction: 'top',
          offset: [0, -8],
          sticky: true,
        });

        marker.on('click', function() {
          emitEvent('map_location_selected', { location_id: locationId });
        });
        marker.on('keypress', function(evt) {
          var key = evt && evt.originalEvent && evt.originalEvent.key;
          if (key === 'Enter' || key === ' ') {
            emitEvent('map_location_selected', { location_id: locationId });
          }
        });

        markerGroup.addLayer(marker);
        markerById[locationId] = marker;
        points.push([lat, lng]);
      });

      map.addLayer(markerGroup);
      window._htMapMarkersById = markerById;

      if (points.length > 0) {
        map.fitBounds(points, { padding: [28, 28] });
      } else {
        map.setView([20, 0], 2);
      }

      _invalidateMapAfterLayout(map, host);
      return { ok: true, marker_count: points.length };
    } catch (error) {
      return {
        ok: false,
        error: (error && error.message) ? error.message : String(error),
      };
    }
  };

  window.htFocusMapLocation = function(locationId) {
    var marker = window._htMapMarkersById && window._htMapMarkersById[String(locationId)];
    var map = window._htMapInstance;
    if (!marker || !map) return false;
    map.setView(marker.getLatLng(), Math.max(map.getZoom(), 8), { animate: true });
    if (typeof marker.openTooltip === 'function') marker.openTooltip();
    return true;
  };
})();
"""


def inject_map_view_assets() -> None:
    """Inject Leaflet dependencies, map styles, and JS bridge helpers."""
    ui.add_head_html(f'<link rel="stylesheet" href="{_LEAFLET_CSS}" crossorigin="anonymous">')
    ui.add_head_html(f'<link rel="stylesheet" href="{_CLUSTER_CSS}">')
    ui.add_head_html(f'<link rel="stylesheet" href="{_CLUSTER_DEFAULT_CSS}">')
    ui.add_head_html(f'<script src="{_LEAFLET_JS}" crossorigin="anonymous"></script>')
    ui.add_head_html(f'<script src="{_CLUSTER_JS}"></script>')
    ui.add_head_html(_MAP_STYLE)
    ui.add_body_html(f"<script>{_MAP_BRIDGE_JS}</script>")


def map_bootstrap_payload(
    locations: list[dict[str, object]],
    use_dark_tiles: bool,
    element_id: str = "ht-map-canvas",
) -> dict[str, object]:
    """Return the payload consumed by window.htRenderMap."""
    tile_url = _OSM_DARK_TILE if use_dark_tiles else _OSM_LIGHT_TILE
    attribution = _OSM_DARK_ATTRIBUTION if use_dark_tiles else _OSM_LIGHT_ATTRIBUTION
    return {
        "element_id": element_id,
        "tile_url": tile_url,
        "attribution": attribution,
        "locations": locations,
    }