/**
 * Cámara para el portal del proveedor — /my/despacho
 * Vanilla JS. Cada foto se sube como página; "Listo" llama a /finalize.
 * Overlay único #imp_cam_overlay reutilizado por todos los documentos.
 */
(function () {
    'use strict';

    let currentDocId = null;
    let stream = null;

    // ── Inyectar overlay ──────────────────────────────────────────────────────
    const overlay = document.createElement('div');
    overlay.id = 'imp_cam_overlay';
    overlay.style.cssText = [
        'display:none', 'position:fixed', 'inset:0', 'background:rgba(0,0,0,.85)',
        'z-index:9999', 'flex-direction:column', 'align-items:center',
        'justify-content:center', 'gap:12px',
    ].join(';');
    overlay.innerHTML = `
        <video id="imp_cam_video" autoplay playsinline
               style="max-width:90vw;max-height:60vh;border-radius:8px;"></video>
        <canvas id="imp_cam_canvas" style="display:none;"></canvas>
        <div style="display:flex;gap:10px;flex-wrap:wrap;justify-content:center;">
            <button id="imp_cam_shoot"  class="btn btn-primary">📷 Capturar</button>
            <button id="imp_cam_done"   class="btn btn-success">✅ Listo</button>
            <button id="imp_cam_cancel" class="btn btn-secondary">✖ Cancelar</button>
        </div>
        <div id="imp_cam_count" style="color:#fff;font-size:.9rem;"></div>`;
    document.body.appendChild(overlay);

    const video   = document.getElementById('imp_cam_video');
    const canvas  = document.getElementById('imp_cam_canvas');
    const btnShoot  = document.getElementById('imp_cam_shoot');
    const btnDone   = document.getElementById('imp_cam_done');
    const btnCancel = document.getElementById('imp_cam_cancel');
    const countEl   = document.getElementById('imp_cam_count');

    // ── Abrir cámara ──────────────────────────────────────────────────────────
    function openCamera(docId) {
        currentDocId = docId;
        overlay.style.display = 'flex';
        navigator.mediaDevices.getUserMedia({
            video: { facingMode: { ideal: 'environment' } }
        }).then(s => {
            stream = s;
            video.srcObject = s;
        }).catch(() => {
            alert('No se pudo acceder a la cámara. Usa "Subir archivo" en su lugar.');
            closeCamera();
        });
        updateCount();
    }

    function closeCamera() {
        if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
        overlay.style.display = 'none';
        currentDocId = null;
    }

    function updateCount() {
        // Leer el badge de páginas del botón que abrió la cámara
        const badge = document.querySelector(
            `.js-imp-cam-open[data-doc-id="${currentDocId}"] .imp-page-badge`);
        const n = badge ? parseInt(badge.textContent) || 0 : 0;
        countEl.textContent = n > 0 ? `${n} página(s) capturada(s)` : '';
    }

    // ── Capturar foto ─────────────────────────────────────────────────────────
    btnShoot.addEventListener('click', () => {
        if (!currentDocId) return;
        canvas.width  = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0);
        canvas.toBlob(blob => {
            if (!blob) return;
            const fd = new FormData();
            fd.append('image', blob, 'page.jpg');
            fetch(`/my/despacho/page/add/${currentDocId}`, {
                method: 'POST', body: fd,
            }).then(r => r.json()).then(data => {
                if (data.ok) {
                    // Actualizar badge en el botón
                    const badge = document.querySelector(
                        `.js-imp-cam-open[data-doc-id="${currentDocId}"] .imp-page-badge`);
                    if (badge) badge.textContent = data.pages;
                    else {
                        const btn = document.querySelector(
                            `.js-imp-cam-open[data-doc-id="${currentDocId}"]`);
                        if (btn) {
                            const b = document.createElement('span');
                            b.className = 'imp-page-badge badge bg-warning ms-1';
                            b.textContent = data.pages;
                            btn.appendChild(b);
                        }
                    }
                    countEl.textContent = `${data.pages} página(s) capturada(s)`;
                } else {
                    alert(data.reason || 'Error al subir la foto.');
                }
            });
        }, 'image/jpeg', 0.85);
    });

    // ── Listo — finalizar ─────────────────────────────────────────────────────
    btnDone.addEventListener('click', () => {
        if (!currentDocId) return;
        const fd = new FormData();
        fetch(`/my/despacho/finalize/${currentDocId}`, { method: 'POST', body: fd })
            .then(() => { closeCamera(); location.reload(); });
    });

    btnCancel.addEventListener('click', closeCamera);

    // ── Delegación de eventos ─────────────────────────────────────────────────
    document.addEventListener('click', e => {
        const btn = e.target.closest('.js-imp-cam-open');
        if (btn) {
            e.preventDefault();
            openCamera(btn.dataset.docId);
        }
    });
})();
