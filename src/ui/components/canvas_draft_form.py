"""On-drop creation form — floating popover for draft device details.

Hides the form HTML, validation, positioning, and submit/cancel flow.
"""

CANVAS_DRAFT_FORM_JS: str = """
(function() {
    window._htShowDraftForm = function(opts, onSubmit, onCancel) {
        var existing = document.getElementById('ht-draft-form');
        if (existing) existing.remove();

        var form = document.createElement('div');
        form.id = 'ht-draft-form';
        form.style.cssText = [
            'position:fixed', 'z-index:10000',
            'background:var(--ht-bg-surface-raised)',
            'border:1px solid var(--ht-border)',
            'border-radius:var(--ht-radius-card)',
            'padding:16px', 'min-width:260px', 'max-width:320px',
            'box-shadow:var(--ht-shadow-lg)',
            'display:flex', 'flex-direction:column', 'gap:10px'
        ].join(';');

        var left = Math.min(opts.screenX || 200, window.innerWidth - 340);
        var top  = Math.min(opts.screenY || 200, window.innerHeight - 380);
        form.style.left = Math.max(0, left) + 'px';
        form.style.top  = Math.max(0, top) + 'px';

        var title = document.createElement('div');
        title.style.cssText = 'font-weight:600;color:var(--ht-text-primary);font-size:0.95rem;';
        title.textContent = 'New ' + (opts.deviceType || 'Device');
        form.appendChild(title);

        function makeField(labelText, id, required, value) {
            var wrap = document.createElement('div');
            wrap.style.cssText = 'display:flex;flex-direction:column;gap:2px;';
            var lbl = document.createElement('label');
            lbl.textContent = labelText + (required ? ' *' : '');
            lbl.style.cssText = 'font-size:0.75rem;color:var(--ht-text-secondary);';
            lbl.setAttribute('for', id);
            var inp = document.createElement('input');
            inp.id = id;
            inp.value = value || '';
            inp.style.cssText = [
                'padding:6px 8px',
                'border-radius:var(--ht-radius-input)',
                'border:1px solid var(--ht-border)',
                'background:var(--ht-bg-surface)',
                'color:var(--ht-text-primary)',
                'font-size:0.875rem'
            ].join(';');
            if (required) inp.setAttribute('required', 'true');
            wrap.appendChild(lbl);
            wrap.appendChild(inp);
            form.appendChild(wrap);
            return inp;
        }

        var nameInput = makeField('Name', 'ht-draft-name', true, '');
        var typeInput = makeField('Type', 'ht-draft-type', false, opts.deviceType || '');
        var ipInput   = makeField('IP', 'ht-draft-ip', false, '');
        var macInput  = makeField('MAC', 'ht-draft-mac', false, '');
        var osInput   = makeField('OS', 'ht-draft-os', false, '');
        var notesInput = makeField('Notes', 'ht-draft-notes', false, '');

        var errDiv = document.createElement('div');
        errDiv.style.cssText = 'color:var(--ht-error);font-size:0.75rem;min-height:1em;';
        form.appendChild(errDiv);

        var btnRow = document.createElement('div');
        btnRow.style.cssText = 'display:flex;gap:8px;justify-content:flex-end;';
        var cancelBtn = document.createElement('button');
        cancelBtn.textContent = 'Cancel';
        cancelBtn.type = 'button';
        cancelBtn.style.cssText = [
            'padding:6px 14px', 'border-radius:var(--ht-radius-input)',
            'border:1px solid var(--ht-border)', 'background:transparent',
            'color:var(--ht-text-secondary)', 'cursor:pointer', 'font-size:0.8rem'
        ].join(';');
        var submitBtn = document.createElement('button');
        submitBtn.textContent = 'Add Draft';
        submitBtn.type = 'button';
        submitBtn.style.cssText = [
            'padding:6px 14px', 'border-radius:var(--ht-radius-input)',
            'border:none', 'background:var(--ht-accent)',
            'color:var(--ht-text-on-accent)', 'cursor:pointer',
            'font-size:0.8rem', 'font-weight:600'
        ].join(';');
        btnRow.appendChild(cancelBtn);
        btnRow.appendChild(submitBtn);
        form.appendChild(btnRow);

        document.body.appendChild(form);
        nameInput.focus();

        function cleanup() { form.remove(); }

        function submit() {
            var name = nameInput.value.trim();
            if (!name) { errDiv.textContent = 'Name is required.'; nameInput.focus(); return; }
            cleanup();
            onSubmit({
                name: name,
                type: typeInput.value.trim() || opts.deviceType || 'Server',
                ip: ipInput.value.trim(),
                mac: macInput.value.trim(),
                os: osInput.value.trim(),
                notes: notesInput.value.trim()
            });
        }

        function cancel() { cleanup(); onCancel(); }

        submitBtn.addEventListener('click', submit);
        cancelBtn.addEventListener('click', cancel);

        nameInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') { e.preventDefault(); submit(); }
            if (e.key === 'Escape') { e.preventDefault(); cancel(); }
        });
        form.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') { e.preventDefault(); cancel(); }
        });

        setTimeout(function() {
            document.addEventListener('mousedown', function dismissOnOutside(e) {
                if (!form.contains(e.target)) {
                    document.removeEventListener('mousedown', dismissOnOutside);
                    cancel();
                }
            });
        }, 50);
    };
})();
"""
