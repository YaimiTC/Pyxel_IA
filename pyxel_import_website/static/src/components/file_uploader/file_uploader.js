/** @odoo-module **/

import { Component, useState, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class FileUploader extends Component {
  setup() {
    this.fileInputRef = useRef('fileInput');
    this.state = useState({
      uploading: false,
      selectedFile: null,
    });
  }

  async onFileChange(ev) {
    const file = ev.target.files[0];

    if (this.fileInputRef.el) {
      this.fileInputRef.el.value = '';
    }

    if (!file) {
      this.state.selectedFile = null;
      return;
    }

    if (!file.name.endsWith(".pdf")) {
      alert("Solo se permiten archivos PDF.");
      this.state.selectedFile = null;
      return;
    }

    this.state.selectedFile = file.name;
    this.state.uploading = true;

    try {
      console.log("Props recibidos:", this.props.model);

      const formData = new FormData();
      formData.append("file", file);
      formData.append("model", this.props.model);
      formData.append("record_id", this.props.recordId);
      formData.append("field_name", this.props.fieldName);
      formData.append("csrf_token", odoo.csrf_token);

      const request = await fetch("/upload_pdf", {
        method: "POST",
        body: formData,
      });

      if (!request.ok) {
        throw new Error(`Error HTTP: ${request.status} ${request.statusText}`);
      }
      const response = await request.json();
      if (response.success) {
        if (this.env?.services?.notification) {
          this.env.services.notification.add("Archivo PDF subido correctamente", {
            type: "success",
            sticky: false,
          });
        }
        window.location.reload(); // o trigger de evento si estás en SPA
      } else {
        throw new Error(response.error || "Error desconocido al subir el archivo");
      }

    } catch (error) {
      this.state.uploading = false;
      alert(`Error al subir el archivo: ${error.message}`);
      this.state.selectedFile = null;
    }
  }
  clearFile() {
    if (this.fileInputRef.el) {
      this.fileInputRef.el.value = '';
    }
    this.state.selectedFile = null;
  }
  triggerFileInput(ev) {
    ev.preventDefault(); // Prevent any default button behavior
    if (this.fileInputRef.el) {
      this.fileInputRef.el.click();
    }
  }
}

FileUploader.template = "pyxel_import_website.FileUploader";
registry.category("public_components").add("pyxel_import_website.FileUploader", FileUploader);
console.log('Se registra el componente al parecer')