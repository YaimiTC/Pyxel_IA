/** @odoo-module **/
/**
 * Widget OWL "camera_capture" para la ficha de revisión del documento de importación.
 * El revisor toma fotos o sube archivos; las imágenes se acumulan en estado local.
 * Al pulsar "Generar PDF y aplicar" se envían al servidor (action_assemble_from_images)
 * que usa Pillow para hacer el PDF y lo guarda en el attachment. Luego recarga el record.
 */
import { Component, useState, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";

class CameraCaptureField extends Component {
    static template = "pyxel_enetradex_backend.CameraCaptureField";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ cameraOpen: false, pages: [], loading: false });
        this.videoRef = useRef("video");
        this.canvasRef = useRef("canvas");
        this._stream = null;
    }

    get cameraOpen() { return this.state.cameraOpen; }
    get pages()      { return this.state.pages; }
    get loading()    { return this.state.loading; }

    // ── Cámara ────────────────────────────────────────────────────────────────
    async openCamera() {
        try {
            this._stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: { ideal: 'environment' } },
            });
            this.state.cameraOpen = true;
            await Promise.resolve(); // esperar render
            if (this.videoRef.el) this.videoRef.el.srcObject = this._stream;
        } catch {
            this.notification.add('No se pudo acceder a la cámara. Usa "Subir archivo".', { type: 'warning' });
        }
    }

    closeCamera() {
        if (this._stream) { this._stream.getTracks().forEach(t => t.stop()); this._stream = null; }
        this.state.cameraOpen = false;
    }

    shoot() {
        const video  = this.videoRef.el;
        const canvas = this.canvasRef.el;
        if (!video || !canvas) return;
        canvas.width  = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0);
        // Guardar como data URL para previsualización y como base64 para el servidor
        const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
        const b64 = dataUrl.split(',')[1];
        this.state.pages.push({ preview: dataUrl, b64 });
    }

    removePage(idx) {
        this.state.pages.splice(idx, 1);
    }

    // ── Subida de archivo ─────────────────────────────────────────────────────
    async onFileChange(ev) {
        const file = ev.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = e => {
            const b64 = e.target.result.split(',')[1];
            const preview = e.target.result;
            // Si es PDF no se puede previsualizar directamente — mostrar ícono
            const isImage = file.type.startsWith('image/');
            this.state.pages.push({
                preview: isImage ? preview : null,
                b64,
                filename: file.name,
                isPdf: !isImage,
            });
        };
        reader.readAsDataURL(file);
        ev.target.value = '';
    }

    // ── Enviar al servidor ────────────────────────────────────────────────────
    async buildPdf() {
        if (!this.state.pages.length) return;
        const recordId = this.props.record.resId;
        if (!recordId) {
            this.notification.add('Guarda el registro antes de generar el PDF.', { type: 'warning' });
            return;
        }
        this.state.loading = true;
        try {
            const images = this.state.pages.map(p => p.b64);
            await this.orm.call(
                'pyxel.import.document',
                'action_assemble_from_images',
                [[recordId], images],
            );
            this.state.pages = [];
            this.closeCamera();
            // Recargar el record para ver el nuevo attachment
            await this.props.record.load();
            this.notification.add('PDF generado y aplicado correctamente.', { type: 'success' });
        } catch (e) {
            this.notification.add('Error al generar el PDF: ' + (e.message || e), { type: 'danger' });
        } finally {
            this.state.loading = false;
        }
    }
}

registry.category("fields").add("camera_capture", {
    component: CameraCaptureField,
    supportedTypes: ["binary"],
});
