/** @odoo-module **/
import { browser } from "@web/core/browser/browser";
import { Tooltip } from "@web/core/tooltip/tooltip";
import { usePopover } from "@web/core/popover/popover_hook";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, useRef, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class FileUploader extends Component {
  static notificationShown = new Set();

  setup() {
    // Inits
    this.fileInputRef = useRef("fileInput");
    this.infoIconRef = useRef("infoIcon");
    this.state = useState({
      uploading: false,
      selectedFile: null,
    });
    this.popover = usePopover(Tooltip);
    this.notification = useService("notification");

    // Checking for permissions onMounted
    onMounted(() => {
      if (this.cannotUpload) {
        const notificationKey = `disabled_${this.props.recordId}`;
        const alreadyNotified = FileUploader.notificationShown.has(notificationKey);
        if (!alreadyNotified) {
          this.triggerNotifications();
          FileUploader.notificationShown.add(notificationKey);
        }
      }
    });
  }

  get cannotUpload() {
    return this.props.cannotUpload;
  }

  get disableMessage() {
    return this.props.disableMessage;
  }

  async onFileChange(ev) {
    const file = ev.target.files[0];

    if (this.fileInputRef.el) {
      this.fileInputRef.el.value = "";
    }

    if (!file) {
      this.state.selectedFile = null;
      return;
    }

    if (!file.name.endsWith(".pdf")) {
      this.notification.add("Solo se permiten archivos en formato PDF.", {
        type: "warning",
        title: "Archivo no permitido",
      });
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
          this.env.services.notification.add(
            "Archivo PDF subido correctamente",
            {
              type: "success",
              sticky: false,
            },
          );
        }
        window.location.reload(); // o trigger de evento si estás en SPA
      } else {
        throw new Error(
          response.error || "Error desconocido al subir el archivo",
        );
      }
    } catch (error) {
      this.state.uploading = false;
      this.notification.add(
        `Se ha detectado un error al subir el archivo: ${error.message}`,
        {
          type: "warning",
          title: "Error",
        },
      );
      this.state.selectedFile = null;
    }
  }

  clearFile() {
    if (this.fileInputRef.el) {
      this.fileInputRef.el.value = "";
    }
    this.state.selectedFile = null;
  }

  triggerFileInput(ev) {
    // Fallback: If user still manages to interact (via tab navigation), notify
    if (this.cannotUpload) {
      this.triggerNotifications();
    }
    ev.preventDefault(); // Prevent any default button behavior
    if (this.fileInputRef.el) {
      this.fileInputRef.el.click();
    }
  }

  triggerNotifications() {
    // Triggering notification service
    this.notification.add(
      this.disableMessage || "No tiene permisos para cargar archivos",
      {
        type: "warning",
        title: "Acción no permitida",
      },
    );
    if (this.infoIconRef.el) {
      // Triggering temporal popover
      this.popover.open(this.infoIconRef.el, {
        tooltip: this.disableMessage,
      });
      browser.setTimeout(this.popover.close, 3500);
    }
  }
}

FileUploader.template = "pyxel_import_website.FileUploader";
registry
  .category("public_components")
  .add("pyxel_import_website.FileUploader", FileUploader);
console.log("Se registra el componente al parecer");
