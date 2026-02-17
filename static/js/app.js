// App State
let currentLicense = null;

// Modal Functions
function openModal(modalId) {
    document.getElementById(modalId).classList.remove('hidden');
    document.getElementById('modal-overlay').classList.remove('hidden');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.add('hidden');

    // Si cerramos todos los modales, ocultar overlay
    const modals = document.querySelectorAll('.modal:not(.hidden)');
    if (modals.length === 0) {
        document.getElementById('modal-overlay').classList.add('hidden');
    }
}

// Close modals on overlay click
document.getElementById('modal-overlay').addEventListener('click', () => {
    document.querySelectorAll('.modal').forEach(modal => modal.classList.add('hidden'));
    document.getElementById('modal-overlay').classList.add('hidden');
});

// Clipboard
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        // Podríamos mostrar un toast aquí
        alert('Código copiado: ' + text);
    });
}

// Detail Modal Population
function handleDetailClick(btn) {
    try {
        const data = JSON.parse(btn.dataset.license);
        openDetailModal(data);
    } catch (e) {
        console.error('Error parsing license data', e);
        alert('Error al abrir detalles');
    }
}

function openDetailModal(licenseData) {
    currentLicense = licenseData;

    // Populate header
    document.getElementById('detail-code').textContent = licenseData.license_code;
    const statusBadge = document.getElementById('detail-status');
    statusBadge.textContent = licenseData.status;
    statusBadge.className = `badge badge-status status-${licenseData.status}`;

    // Populate Edit Form
    document.getElementById('edit-form').action = `/licenses/${licenseData.id}/update`;
    document.getElementById('detail-client').value = licenseData.client_name || '';
    document.getElementById('detail-phone').value = licenseData.client_phone || '';
    document.getElementById('detail-notes').value = licenseData.notes || '';
    document.getElementById('detail-max-devices').value = licenseData.max_devices;

    // Populate Actions
    const renewForm = document.getElementById('renew-form');
    const renewBtn = renewForm.querySelector('button[type="submit"]');

    if (licenseData.status === 'expired') {
        renewForm.action = `/licenses/${licenseData.id}/reactivate`;
        renewBtn.textContent = 'Reactivar (Reiniciar Fecha)';
        renewBtn.classList.remove('btn-primary');
        renewBtn.classList.add('btn-warning');
    } else {
        // Active, Pending, Blocked (blocked usually needs unblock first, but extending validity is valid)
        renewForm.action = `/licenses/${licenseData.id}/extend`;
        renewBtn.textContent = 'Extender (Sumar Días)';
        renewBtn.classList.remove('btn-warning');
        renewBtn.classList.add('btn-primary');
    }

    // Block Toggle Button
    const blockForm = document.getElementById('block-form');
    blockForm.action = `/licenses/${licenseData.id}/toggle-block`;
    const blockBtn = document.getElementById('btn-block-toggle');
    if (licenseData.status === 'blocked') {
        blockBtn.textContent = 'Desbloquear Licencia';
        blockBtn.className = 'btn btn-secondary full-width';
    } else {
        blockBtn.textContent = 'Bloquear Licencia';
        blockBtn.className = 'btn btn-danger full-width'; // Red for block action
    }

    // Delete Action
    document.getElementById('delete-form').action = `/licenses/${licenseData.id}/delete`;

    // Advanced Actions
    document.getElementById('reset-devices-form').action = `/licenses/${licenseData.id}/reset-devices`;
    document.getElementById('regenerate-code-form').action = `/licenses/${licenseData.id}/regenerate-code`;

    // Populate Devices
    const deviceList = document.getElementById('device-list');
    deviceList.innerHTML = '';
    const devices = licenseData.device_ids || [];
    document.getElementById('device-count').textContent = devices.length;

    if (devices.length === 0) {
        deviceList.innerHTML = '<li style="color: var(--text-muted); font-style: italic;">Sin dispositivos registrados</li>';
    } else {
        devices.forEach(device => {
            const li = document.createElement('li');
            li.className = 'device-item';
            li.innerHTML = `
                <span>${device}</span>
                <button class="btn-icon" onclick="removeDevice('${licenseData.id}', '${device}')" title="Desvincular">
                    &times;
                </button>
            `;
            deviceList.appendChild(li);
        });
    }

    openModal('detail-modal');
}

// Open confirmation
function openConfirmDialog() {
    openModal('confirm-modal');
}

// Remove Device Handler
function removeDevice(licenseId, deviceId) {
    if (!confirm(`¿Desvincular dispositivo ${deviceId}?`)) return;

    fetch(`/licenses/${licenseId}/remove-device`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ device_id: deviceId })
    })
        .then(response => {
            if (response.ok) {
                window.location.reload();
            } else {
                alert('Error al eliminar dispositivo');
            }
        });
}

// Duplicate License
function duplicateLicenseFromDetail() {
    if (!currentLicense) return;

    // Close detail modal
    closeModal('detail-modal');

    // Open create modal
    openModal('create-modal');

    // Pre-fill fields
    const typeSelect = document.getElementById('create-type');
    typeSelect.value = currentLicense.license_type;

    // Update days input visibility/value
    if (typeof updateDaysInput === 'function') {
        updateDaysInput();
    }

    // If Custom, restore the original days_valid if available
    // For now we don't have days_valid in license object in UI (it's in DB but not necessarily in the JSON unless we explicitly select it or it's implicitly there)
    // Supabase select * includes it.
    if (currentLicense.license_type === 'CUSTOM') {
        document.getElementById('create-days').value = currentLicense.days_valid || '';
    }

    // Fill other fields
    document.querySelector('textarea[name="notes"]').value = currentLicense.notes || '';
}

// WhatsApp Sharing
function formatWhatsAppMessage(license) {
    let msg = `*LICENCIA EVENTSTORE*\n\n`;
    msg += `🆔 *Código:* \`${license.license_code}\`\n`;
    msg += `👤 *Cliente:* ${license.client_name || 'N/A'}\n`;
    msg += `📋 *Tipo:* ${license.license_type}\n`;

    if (license.status === 'active' && license.days_remaining !== null) {
        msg += `✅ *Estado:* Activa (${license.days_remaining} días restantes)\n`;
        // We might want exact date too
        // msg += `📅 *Vence:* ${license.end_date.split('T')[0]}\n`; 
    } else {
        msg += `ℹ️ *Estado:* ${license.status.toUpperCase()}\n`;
    }

    msg += `📱 *Dispositivos:* ${license.device_ids ? license.device_ids.length : 0}`;
    if (license.max_devices) {
        msg += ` / ${license.max_devices}`;
    }
    msg += `\n`;

    if (license.notes) {
        msg += `📝 *Notas:* ${license.notes}\n`;
    }

    return encodeURIComponent(msg);
}

function shareLicenseOnWhatsApp() {
    if (!currentLicense) return;

    const phone = currentLicense.client_phone;
    if (!phone) {
        alert('⚠️ Esta licencia no tiene un número de teléfono asociado.\n\nPor favor edita la licencia y agrega el teléfono del cliente.');
        return;
    }

    // Basic cleanup of phone number (remove spaces, etc if needed, though usually better if stored clean)
    // Assuming DB stores usable format or user inputs it. 
    // If it doesn't have country code, WA might fail or open blank chat.
    // Let's rely on what's in DB for now, maybe strip non-numeric/plus
    const cleanPhone = phone.replace(/[^0-9+]/g, '');

    const text = formatWhatsAppMessage(currentLicense);
    const url = `https://wa.me/${cleanPhone}?text=${text}`;

    window.open(url, '_blank');
}
