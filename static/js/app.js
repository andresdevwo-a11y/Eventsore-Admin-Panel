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
