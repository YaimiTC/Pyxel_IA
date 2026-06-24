/* Portal — subida de foto para expediente de acreditación */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('.en-photo-widget').forEach(function (widget) {
            initPhotoWidget(widget);
        });
    });

    function initPhotoWidget(widget) {
        var docId    = widget.dataset.docId;
        var btnCam   = widget.querySelector('.en-btn-camera');
        var btnGen   = widget.querySelector('.en-btn-generate');
        var btnForce = widget.querySelector('.en-btn-force');
        var btnDiscard = widget.querySelector('.en-btn-discard');
        var videoWrap  = widget.querySelector('.en-camera-wrap');
        var videoEl    = widget.querySelector('video');
        var thumbsOk   = widget.querySelector('.en-thumbs-ok');
        var thumbsBad  = widget.querySelector('.en-thumbs-bad');
        var badSection = widget.querySelector('.en-rejected-section');
        var okSection  = widget.querySelector('.en-ok-section');
        var msgEl      = widget.querySelector('.en-msg');
        var imgInput   = widget.querySelector('.en-img-input');

        var stream = null;
        var pages = [];     // {page_id, page_number, quality_ok, quality_reason, preview}
        var rejected = [];

        function isMobile() {
            return /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent);
        }

        function showMsg(text, type) {
            msgEl.textContent = text;
            msgEl.className = 'en-msg alert alert-' + (type || 'info') + ' py-1 mt-2';
            msgEl.classList.remove('d-none');
            setTimeout(function () { msgEl.classList.add('d-none'); }, 4000);
        }

        function updateUI() {
            var hasPages    = pages.length > 0;
            var hasRejected = rejected.length > 0;
            okSection.classList.toggle('d-none', !hasPages);
            badSection.classList.toggle('d-none', !hasRejected);
            btnGen.classList.toggle('d-none', !hasPages);
            btnForce.classList.toggle('d-none', !hasRejected);
            btnDiscard.classList.toggle('d-none', !hasRejected);

            thumbsOk.innerHTML = '';
            pages.forEach(function (p) {
                var div = document.createElement('div');
                div.className = 'position-relative d-inline-block me-2 mb-2';
                div.innerHTML =
                    '<img src="' + p.preview + '" style="width:80px;height:80px;object-fit:cover" class="img-thumbnail"/>' +
                    '<span class="badge bg-success position-absolute bottom-0 start-0" style="font-size:9px">Pág ' + p.page_number + '</span>' +
                    '<button type="button" class="btn-close position-absolute top-0 end-0" style="font-size:8px" data-pid="' + p.page_id + '"></button>';
                div.querySelector('.btn-close').addEventListener('click', function () {
                    removePage(p.page_id);
                });
                thumbsOk.appendChild(div);
            });

            thumbsBad.innerHTML = '';
            rejected.forEach(function (r) {
                var div = document.createElement('div');
                div.className = 'd-flex align-items-center gap-2 small';
                div.innerHTML = '<img src="' + r.preview + '" style="width:48px;height:48px;object-fit:cover" class="img-thumbnail"/>' +
                    '<span>Pág ' + r.page_number + ': ' + r.quality_reason + '</span>';
                thumbsBad.appendChild(div);
            });
        }

        function removePage(pageId) {
            pages = pages.filter(function (p) { return p.page_id !== pageId; });
            fetch('/web/dataset/call_kw', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    jsonrpc: '2.0', method: 'call', id: 1,
                    params: {
                        model: 'pyxel.lead.document.page',
                        method: 'unlink',
                        args: [[pageId]],
                        kwargs: {},
                    }
                })
            });
            updateUI();
        }

        function toBase64(file) {
            return new Promise(function (resolve, reject) {
                var r = new FileReader();
                r.onload = function () { resolve(r.result.split(',')[1]); };
                r.onerror = reject;
                r.readAsDataURL(file);
            });
        }

        function toDataUrl(file) {
            return new Promise(function (resolve, reject) {
                var r = new FileReader();
                r.onload = function () { resolve(r.result); };
                r.onerror = reject;
                r.readAsDataURL(file);
            });
        }

        function processImages(images) {
            var b64List = images.map(function (i) { return i.b64; });
            fetch('/my/acreditacion/photo/' + docId, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ images: b64List }),
            })
            .then(function (r) { return r.json(); })
            .then(function (result) {
                if (result.error) { showMsg(result.error, 'danger'); return; }
                result.pages.forEach(function (p, idx) {
                    p.preview = images[idx] ? images[idx].dataUrl : '';
                    pages.push(p);
                });
                result.rejected.forEach(function (p, idx) {
                    p.preview = images[result.pages.length + idx] ? images[result.pages.length + idx].dataUrl : '';
                    rejected.push(p);
                });
                if (result.rejected.length)
                    showMsg(result.rejected.length + ' foto(s) con baja calidad. Puedes forzar el PDF igualmente.', 'warning');
                if (result.pages.length)
                    showMsg(result.pages.length + ' foto(s) añadidas.', 'success');
                updateUI();
            })
            .catch(function () { showMsg('Error al procesar las fotos.', 'danger'); });
        }

        function doAssemble(force) {
            btnGen.disabled = true;
            btnForce.disabled = true;
            fetch('/my/acreditacion/assemble/' + docId, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ force: !!force }),
            })
            .then(function (r) { return r.json(); })
            .then(function (result) {
                if (result.error) { showMsg(result.error, 'danger'); btnGen.disabled = false; btnForce.disabled = false; return; }
                pages = [];
                rejected = [];
                updateUI();
                showMsg('PDF generado. La página se actualizará...', 'success');
                setTimeout(function () { window.location.reload(); }, 1500);
            })
            .catch(function () {
                showMsg('Error al generar el PDF.', 'danger');
                btnGen.disabled = false;
                btnForce.disabled = false;
            });
        }

        /* ── Cámara ── */
        btnCam.addEventListener('click', function () {
            if (isMobile()) {
                imgInput.click();
                return;
            }
            navigator.mediaDevices.getUserMedia({ video: true })
                .then(function (s) {
                    stream = s;
                    videoEl.srcObject = s;
                    videoWrap.classList.remove('d-none');
                })
                .catch(function () {
                    imgInput.click();
                });
        });

        widget.querySelector('.en-btn-capture').addEventListener('click', function () {
            var canvas = document.createElement('canvas');
            canvas.width = videoEl.videoWidth;
            canvas.height = videoEl.videoHeight;
            canvas.getContext('2d').drawImage(videoEl, 0, 0);
            var dataUrl = canvas.toDataURL('image/jpeg', 0.92);
            processImages([{ b64: dataUrl.split(',')[1], dataUrl: dataUrl }]);
        });

        widget.querySelector('.en-btn-close-cam').addEventListener('click', function () {
            if (stream) { stream.getTracks().forEach(function (t) { t.stop(); }); stream = null; }
            videoWrap.classList.add('d-none');
        });

        imgInput.addEventListener('change', function (ev) {
            var files = Array.from(ev.target.files || []);
            ev.target.value = '';
            if (!files.length) return;
            Promise.all(files.map(function (f) {
                return Promise.all([toBase64(f), toDataUrl(f)]).then(function (res) {
                    return { b64: res[0], dataUrl: res[1] };
                });
            })).then(function (images) { processImages(images); });
        });

        btnGen.addEventListener('click', function () { doAssemble(false); });
        btnForce.addEventListener('click', function () { doAssemble(true); });

        btnDiscard.addEventListener('click', function () {
            var ids = rejected.map(function (r) { return r.page_id; });
            if (ids.length) {
                fetch('/web/dataset/call_kw', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        jsonrpc: '2.0', method: 'call', id: 1,
                        params: { model: 'pyxel.lead.document.page', method: 'unlink', args: [ids], kwargs: {} }
                    })
                });
            }
            rejected = [];
            updateUI();
        });

        updateUI();
    }
})();
