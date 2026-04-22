"""Stencil drop handler bridge for the topology canvas event bundle."""

STENCIL_DROP_HANDLER_JS = """
        document.addEventListener('ht:stencil-drop', function(evt) {
            if (window.HT_READONLY) return;
            var d = evt.detail;
            if (!window._cy) return;
            var deviceId = String(d.deviceId || '');
            if (!deviceId) return;

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

            if (window.scheduleAutosave) window.scheduleAutosave(800);

            document.dispatchEvent(new CustomEvent('ht:stencil-placed', {
                detail: { deviceId: deviceId }
            }));

            _notify('Device placed on canvas.', 'positive');
        });
"""