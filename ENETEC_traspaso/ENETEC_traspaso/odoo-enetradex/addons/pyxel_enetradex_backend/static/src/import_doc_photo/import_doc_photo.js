/** @odoo-module **/

import { Component, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Widget para expedientes de acreditación e importación.
 * - "Subir PDF": selector de archivos filtrado a .pdf, máx 6 MB, sube directo.
 * - "Tomar foto": getUserMedia en escritorio | capture en móvil.
 *   Las fotos se acumulan como páginas, se valida calidad, y se ensamblan en PDF.
 */
export class ImportDocPhoto extends Component {
    static template = "pyxel_enetradex_backend.ImportDocPhoto";
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.pdfInput = useRef("pdfInput");
        this.imgInput = useRef("imgInput");
        this.videoRef = useRef("videoEl");
        this.state = useState({
            busy: false,
            assembling: false,
            showCamera: false,
            pages: [],      // {page_id, page_number, quality_score, quality_ok, quality_reason, preview}
            rejected: [],
            stream: null,
        });
    }

    get model() {
        return this.props.record.resModel || "pyxel.import.document";
    }

    get docId() {
        return this.props.record.resId;
    }

    get pageModel() {
        return this.model + ".page";
    }

    // ── PDF ──────────────────────────────────────────────────────────────
    triggerPdf() {
        if (!this.state.busy) this.pdfInput.el.click();
    }

    async onPdfSelected(ev) {
        const file = (ev.target.files || [])[0];
        ev.target.value = "";
        if (!file) return;
        // Validaciones cliente-side
        if (!file.name.toLowerCase().endsWith(".pdf")) {
            this.notification.add(_t("Solo se permiten archivos PDF."), { type: "danger" });
            return;
        }
        if (file.size > 6 * 1024 * 1024) {
            this.notification.add(
                _t("El PDF supera 6 MB (%.1f MB). Comprime el archivo.").replace("%.1f", (file.size / 1024 / 1024).toFixed(1)),
                { type: "danger" }
            );
            return;
        }
        this.state.busy = true;
        try {
            const record = this.props.record;
            if (!record.resId) await record.save();
            const b64 = await this._toBase64(file);
            await this.orm.call(this.model, "upload_pdf_b64", [[this.docId], b64, file.name]);
            await record.load();
            this.notification.add(_t("PDF subido correctamente."), { type: "success" });
        } catch (e) {
            this.notification.add(_t("Error al subir el PDF."), { type: "danger" });
            throw e;
        } finally {
            this.state.busy = false;
        }
    }

    // ── CÁMARA ───────────────────────────────────────────────────────────
    async triggerCamera() {
        if (this.state.busy || this.state.assembling) return;
        // En móvil: input[capture] es suficiente
        if (/Mobi|Android|iPhone|iPad/i.test(navigator.userAgent)) {
            this.imgInput.el.click();
            return;
        }
        // En escritorio: getUserMedia
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true });
            this.state.stream = stream;
            this.state.showCamera = true;
            // Asignar el stream al video element tras el render
            setTimeout(() => {
                if (this.videoRef.el) this.videoRef.el.srcObject = stream;
            }, 100);
        } catch {
            // Si no hay cámara, abrir selector de imágenes como fallback
            this.imgInput.el.click();
        }
    }

    captureFrame() {
        const video = this.videoRef.el;
        if (!video) return;
        const canvas = document.createElement("canvas");
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext("2d").drawImage(video, 0, 0);
        const dataUrl = canvas.toDataURL("image/jpeg", 0.92);
        this._processImages([{ b64: dataUrl.split(",")[1], dataUrl, name: "foto.jpg" }]);
    }

    closeCamera() {
        if (this.state.stream) {
            this.state.stream.getTracks().forEach((t) => t.stop());
            this.state.stream = null;
        }
        this.state.showCamera = false;
    }

    async onImgSelected(ev) {
        const files = [...(ev.target.files || [])];
        ev.target.value = "";
        if (!files.length) return;
        const images = await Promise.all(
            files.map(async (f) => ({ b64: await this._toBase64(f), dataUrl: await this._toDataUrl(f), name: f.name }))
        );
        this._processImages(images);
    }

    async _processImages(images) {
        const record = this.props.record;
        if (!record.resId) await record.save();
        this.state.busy = true;
        try {
            const result = await this.orm.call(
                this.pageModel, "create_from_b64",
                [this.docId, images.map((i) => i.b64)]
            );
            result.pages.forEach((p, idx) => {
                p.preview = images[idx]?.dataUrl || "";
                this.state.pages.push(p);
            });
            result.rejected.forEach((p, idx) => {
                p.preview = images[result.pages.length + idx]?.dataUrl || "";
                this.state.rejected.push(p);
            });
            if (result.rejected.length)
                this.notification.add(
                    _t("%d foto(s) rechazadas por baja calidad.").replace("%d", result.rejected.length),
                    { type: "warning" }
                );
            if (result.pages.length)
                this.notification.add(
                    _t("%d foto(s) añadidas.").replace("%d", result.pages.length),
                    { type: "success" }
                );
        } catch (e) {
            this.notification.add(_t("Error al procesar las fotos."), { type: "danger" });
            throw e;
        } finally {
            this.state.busy = false;
        }
    }

    async assemblePdf() {
        if (!this.state.pages.length) {
            this.notification.add(_t("No hay fotos para generar el PDF."), { type: "warning" });
            return;
        }
        await this._doAssemble(false);
    }

    async assemblePdfForce() {
        await this._doAssemble(true);
    }

    async _doAssemble(force) {
        this.state.assembling = true;
        try {
            await this.orm.call(this.pageModel, "assemble_pdf", [this.docId, force]);
            this.state.pages = [];
            this.state.rejected = [];
            this.closeCamera();
            await this.props.record.load();
            this.notification.add(_t("PDF generado y enviado a la IA."), { type: "success" });
        } catch (e) {
            this.notification.add(_t("Error al generar el PDF."), { type: "danger" });
            throw e;
        } finally {
            this.state.assembling = false;
        }
    }

    removePage(pageId) {
        this.state.pages = this.state.pages.filter((p) => p.page_id !== pageId);
        this.orm.unlink(this.pageModel, [pageId]).catch(() => {});
    }

    clearRejected() {
        const ids = this.state.rejected.map((r) => r.page_id);
        if (ids.length) this.orm.unlink(this.pageModel, ids).catch(() => {});
        this.state.rejected = [];
    }

    // ── Utils ─────────────────────────────────────────────────────────────
    _toBase64(file) {
        return new Promise((resolve, reject) => {
            const r = new FileReader();
            r.onload = () => resolve(r.result.split(",")[1]);
            r.onerror = reject;
            r.readAsDataURL(file);
        });
    }

    _toDataUrl(file) {
        return new Promise((resolve, reject) => {
            const r = new FileReader();
            r.onload = () => resolve(r.result);
            r.onerror = reject;
            r.readAsDataURL(file);
        });
    }
}

registry.category("view_widgets").add("en_doc_photo", { component: ImportDocPhoto });
