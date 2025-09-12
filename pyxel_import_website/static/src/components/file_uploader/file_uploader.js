/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class FileUploader extends Component {
  setup() {
    this.state = useState({ uploading: false });
  }

  async onFileChange(ev) {
    const file = ev.target.files[0];
    if (!file || !file.name.endsWith(".pdf")) {
      alert("Solo se permiten archivos PDF.");
      return;
    }

    this.state.uploading = true;
    console.log("Props recibidos:", this.props.model);
    const formData = new FormData();
    formData.append("file", file);
    formData.append("model", this.props.model);
    formData.append("record_id", this.props.recordId);
    formData.append("field_name", this.props.fieldName);
    formData.append("csrf_token", odoo.csrf_token);

    const response = await fetch("/upload_pdf", {
      method: "POST",
      body: formData,
    });

    const result = await response.json();
    this.state.uploading = false;
    if (result.success) {
      window.location.reload(); // o trigger de evento si estás en SPA
    } else {
      alert(result.error);
    }
  }
}

FileUploader.template = "pyxel_import_website.FileUploader";
registry.category("public_components").add("pyxel_import_website.FileUploader", FileUploader);
console.log('Se registra el componente al parecer')