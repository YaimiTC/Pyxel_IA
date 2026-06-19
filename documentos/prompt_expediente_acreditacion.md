# Prompt de integración — Expediente de acreditación (flujo de 3 pasos)

> Pásale este prompt al otro desarrollador (o a su asistente) para reproducir
> la solución completa: modelo, backend, portal y validaciones.

---

Contexto: Odoo 17 Community. Módulo "pyxel_import" dividido en:
- pyxel_import_backend (modelos, vistas backend)
- pyxel_import_website (portal, controladores, templates QWeb + Bootstrap 5)
- pyxel_import_website_interface (interfaz custom del portal; REEMPLAZA el home
  del portal — ver trampa al final)

Idioma del proyecto: español. Existe un validador de documentos con IA (sistema
aparte) que emite un veredicto Apto/Dudoso/Rechazado con confianza (%), calidad
de imagen (%) y datos OCR. Su integración real queda como TODO (hooks marcados).

OBJETIVO: "Expediente de acreditación" para las solicitudes (crm.lead). Hoy los
documentos del formulario web se guardan como ir.attachment sueltos colgando de
res.partner y el comercial no sabe qué documento corresponde a cada concepto.
Hay que estructurarlos con un FLUJO DE VALIDACIÓN DE 3 PASOS SECUENCIALES:
  Paso 1 IA (automático) -> Paso 2 Abogada (manual) -> Paso 3 Comercial (manual).
Cada paso solo se desbloquea si el anterior aprobó. Más una pantalla de revisión
en el backend (previsualizador + reporte IA + notas), envío de notas por correo,
y una vista de portal para el cliente con estado combinado.

================= 1. MODELO pyxel.lead.document =================
Archivo: pyxel_import_backend/models/lead_document.py
_name='pyxel.lead.document', _order='sequence, id'.

Campos base:
- lead_id Many2one('crm.lead', ondelete='cascade', index=True)
- sequence Integer(default=10)
- document_key Char ; document_label Char(required) ; client_type Char
- is_required Boolean(default=True)
- attachment_id Many2one('ir.attachment') ; upload_date Datetime
- document_file = Binary(related='attachment_id.datas', readonly)
- document_filename = Char(related='attachment_id.name', readonly)

PASO 1 — IA (automático):
- ai_state Selection([pending,validating,passed,doubt,rejected], default=pending, required)
  etiquetas Pendiente/Validando/Apto/Dudoso/Rechazado
- ai_confidence Float ; ai_quality Float ; ai_reason Text ; ai_extracted_data Text (OCR)

PASO 2 — Abogada (manual):
- lawyer_state Selection([blocked,to_review,approved,rejected], default=blocked, required)
  etiquetas No aplica/En revisión/Aprobado/Rechazado
- lawyer_notes Text  -> notas INTERNAS (el cliente NO las ve)
- lawyer_reason Text -> motivo de rechazo que SÍ ve el cliente

PASO 3 — Comercial (manual):
- commercial_state Selection([blocked,to_review,approved,rejected], default=blocked, required)
- commercial_reason Text -> motivo de rechazo que SÍ ve el cliente

ESTADO COMBINADO para el portal (computado store=True):
- portal_state Selection([pending,validating,rejected,in_review,approved,optional])
- portal_reason Text
Lógica _compute_portal_state (depends de attachment_id, is_required, ai_state,
ai_reason, lawyer_state, lawyer_reason, commercial_state, commercial_reason):
  * sin attachment y commercial != approved -> pending (u optional si no is_required)
  * ai_state == 'validating' -> validating
  * ai_state in ('doubt','rejected') -> rejected, portal_reason = ai_reason
  * ai_state == 'passed':
      - lawyer_state == 'rejected' -> rejected, portal_reason = lawyer_reason
      - lawyer_state != 'approved' -> in_review (con la abogada)
      - commercial_state == 'approved' -> approved
      - commercial_state == 'rejected' -> rejected, portal_reason = commercial_reason
      - else -> in_review (con la comercial)
El cliente ve un estado ÚNICO: no distingue si está con la abogada o la comercial
(ambos = 'in_review'). El rechazo muestra el motivo de quien rechazó.

DESBLOQUEO SECUENCIAL:
- override write(): si 'ai_state' in vals y queda 'passed' y lawyer_state=='blocked'
  -> lawyer_state='to_review'. (Para que cuando el validador IA externo marque
  Apto, la abogada se active sola. La recursión se corta porque tras el primer
  write lawyer_state ya no es 'blocked'.)
- action_lawyer_approve: exige ai_state=='passed' (si no UserError); set
  lawyer_state='approved', lawyer_reason=False y commercial_state='to_review'.
- action_lawyer_reject: exige ai_state=='passed'; exige lawyer_reason no vacío
  (UserError "el cliente verá ese motivo"); set lawyer_state='rejected',
  commercial_state='blocked'.
- action_lawyer_reopen: si ai_state=='passed' -> lawyer_state='to_review',
  commercial_state='blocked'.
- action_commercial_approve: exige lawyer_state=='approved' (si no UserError);
  set commercial_state='approved', commercial_reason=False.
- action_commercial_reject: exige lawyer_state=='approved'; exige
  commercial_reason no vacío; set commercial_state='rejected'.
- action_commercial_reopen: si lawyer_state=='approved' -> commercial_state='to_review'.

OTROS MÉTODOS:
- action_view_document: ir.actions.act_url a /web/content/<attachment_id>?download=false, target new.
- action_open_review: act_window form view_pyxel_lead_document_form, target current.
- _get_notes_recipients: empresa (lead.partner_id si tiene email) + child_ids con email.
- _build_notes_email_body: HTML con concepto, dictamen IA (etiqueta + confianza),
  ai_reason, y si rejected los motivos de abogada/comercial (NO incluir lawyer_notes).
- action_send_notes_email: si no hay destinatarios UserError; abre wizard
  mail.compose.message modo comment sobre crm.lead (default_model='crm.lead',
  default_res_id=lead.id, default_partner_ids, default_subject, default_body).
  Autor = usuario logueado; envío por servidor saliente institucional; queda en
  el chatter de la oportunidad.
- @api.model get_client_type_for_keys(doc_keys): infiere tipo por prefijo.
- @api.model build_expediente(lead, client_type, uploaded): crea una línea por
  doc del catálogo del tipo; a las que tienen attachment subido les pone
  ai_state='validating' y upload_date=now (los demás estados quedan en default).

CATÁLOGO (constantes de módulo):
DOC_CATALOG = {tipo: [(clave, etiqueta, requerido), ...]} con tipos Mipyme,
Sucursal Extranjera, Estatal, CNA, Proveedor Extranjero; claves y etiquetas
salen del dict DOC_FIELD_LABELS de pyxel_import_website/controllers/main.py
(prefijos doc_mipyme_/doc_sucursal_/doc_estatal_/doc_cna_/doc_prov_; excluir
'doc_adicional'). DOC_PREFIX_TO_TYPE = {prefijo: tipo}.

================= 2. crm.lead =================
Archivo: pyxel_import_backend/models/crm_lead.py (_inherit crm.lead).
- accreditation_document_ids One2many('pyxel.lead.document','lead_id')
- 4 contadores computados sobre los is_required, usando portal_state:
  accreditation_doc_count (total requeridos), accreditation_approved_count
  (portal_state=='approved'), accreditation_review_count (in_review+validating),
  accreditation_pending_count (pending+rejected).

================= 3. __init__ / security / manifest =================
- models/__init__.py: importar lead_document.
- security/ir.model.access.csv: model_pyxel_lead_document -> base.group_user
  (1,1,1,1) y base.group_portal (read=1,write=1,create=0,unlink=1).
- __manifest__.py backend: añadir 'views/lead_document_views.xml'; subir versión.

================= 4. VISTAS BACKEND =================
Archivo: pyxel_import_backend/views/lead_document_views.xml

(a) Ficha de revisión view_pyxel_lead_document_form (mejor usabilidad, NO form plano):
- header con botones type=object:
  Aprobar (legal)  -> action_lawyer_approve, invisible="ai_state != 'passed' or lawyer_state == 'approved'"
  Rechazar (legal) -> action_lawyer_reject,  invisible="ai_state != 'passed' or lawyer_state == 'rejected'"
  Reabrir (legal)  -> action_lawyer_reopen,  invisible="lawyer_state not in ('approved','rejected')"
  Aprobar (comercial)  -> action_commercial_approve, invisible="lawyer_state != 'approved' or commercial_state == 'approved'"
  Rechazar (comercial) -> action_commercial_reject,  invisible="lawyer_state != 'approved' or commercial_state == 'rejected'"
  Reabrir (comercial)  -> action_commercial_reopen,  invisible="commercial_state not in ('approved','rejected')"
  Enviar notas por correo -> action_send_notes_email, invisible="not attachment_id"
- sheet: oe_title (document_label + client_type) y <div class="row">:
  Col izq (col-lg-7): card "Documento subido" con
    <field name="document_file" filename="document_filename" widget="pdf_viewer"/>
    (mensaje si no attachment_id) + botón action_view_document.
  Col der (col-lg-5), TRES cards:
    1) "Análisis de la IA": badge ai_state (decoration-success passed / warning
       doubt / danger rejected / info validating); ai_confidence y ai_quality con
       widget="progressbar" readonly; ALERTA roja invisible="ai_state != 'rejected'"
       ("La IA rechazó el documento"); ALERTA amarilla invisible="ai_state != 'doubt'"
       ("La IA lo marcó como dudoso"); bloque "Lo que reporta la IA" con ai_reason
       (invisible si vacío); bloque "Datos extraídos (OCR)" con ai_extracted_data.
    2) "Revisión de la abogada" invisible="ai_state != 'passed'": badge lawyer_state;
       lawyer_notes (rotulado "Notas internas (el cliente NO las ve)"); lawyer_reason
       (rotulado "Motivo de rechazo (lo ve el cliente)").
    3) "Revisión comercial" invisible="lawyer_state != 'approved'": badge
       commercial_state; commercial_reason (rotulado "Motivo de rechazo (lo ve el cliente)").
  TRAMPA: todo <label> dentro del form debe tener for= a un campo, o usar
  class="o_form_label"; para textos decorativos usa <span>, si no rompe la validación.

(b) Heredar crm.crm_lead_view_form: xpath //notebook position=inside ->
  <page string="Documentación de acreditación" invisible="accreditation_doc_count == 0">
  con group de los 4 contadores y un tree editable="bottom" create="0" delete="0"
  sobre accreditation_document_ids con columnas readonly: document_label,
  attachment_id, ai_state (decorations), ai_confidence, lawyer_state (string
  "Abogada", decorations), commercial_state (string "Comercial", decorations),
  portal_state (string "Estado cliente", decorations) y botones por fila:
  "Revisar" (action_open_review) y "Ver" (action_view_document), ambos
  invisible="not attachment_id". (Las aprobaciones se hacen en la ficha, no en el tree.)

================= 5. CONECTAR EL FORMULARIO WEB =================
pyxel_import_website/controllers/main.py, website_form, rama model=='crm.lead'
y register_type=='accreditation':
- En el bucle que crea los ir.attachment doc_*, recolectar {base_key: attachment.id}
  (excluir 'doc_adicional') y guardarlo en request.session ('accreditation_docs'
  + 'accreditation_partner_id').
- DESPUÉS de super().website_form() (que crea el lead; el lead NO existe antes),
  método _build_accreditation_expediente(): buscar lead por partner_id (id desc,
  limit 1), inferir client_type y llamar build_expediente(lead, client_type, uploaded).
No romper el flujo actual (los ir.attachment en res.partner se siguen creando).

================= 6. PORTAL DEL CLIENTE =================
Controlador pyxel_import_website/controllers/portal_controller.py (clase
Portal(CustomerPortal)). Importar content_disposition de odoo.http.
- helpers _get_accreditation_lead() y _get_user_doc(doc_id) (verifica que
  doc.lead_id.partner_id == commercial_partner_id).
- /my/acreditacion (auth=user, website): render portal_my_accreditation.
- /my/acreditacion/download/<int:doc_id> (auth=user): make_response del attachment.
- /my/acreditacion/delete/<int:doc_id> (POST): SOLO si portal_state not in
  ('in_review','approved'); borra attachment y resetea (attachment_id=False,
  upload_date=False, ai_state='pending', ai_reason=False, ai_confidence=0,
  ai_quality=0, lawyer_state='blocked', lawyer_reason=False, lawyer_notes=False,
  commercial_state='blocked', commercial_reason=False).
- /my/acreditacion/upload/<int:doc_id> (POST, csrf=False): SOLO si portal_state in
  ('pending','rejected','optional') y archivo PDF; borra anterior, crea ir.attachment
  (res.partner/lead.partner_id.id), set attachment_id, upload_date, ai_state='validating'.
  Dejar # TODO para invocar al validador IA (fija ai_state/ai_confidence/ai_quality/
  ai_reason/ai_extracted_data).
- _prepare_portal_layout_values(): añadir 'accreditation_count' (si
  type_of_contact in ['Client','Supplier']).

Template pyxel_import_website/views/portal_template_view.xml ->
<template id="portal_my_accreditation"> con t-call="portal.portal_layout":
- 4 tarjetas resumen (requeridos/aprobados/en revisión/pendientes).
- por documento, card con badge de doc.portal_state (approved=success,
  in_review=warning, validating=info, rejected=danger, pending=secondary,
  optional=light); si rejected y portal_reason -> alert-danger con el motivo
  (este motivo es el de quien rechazó: IA, abogada o comercial); si in_review ->
  alert "ahora lo revisa nuestro equipo"; si approved -> alert-success.
  REGLAS DE VISIBILIDAD PARA EL CLIENTE:
    * NO mostrar lawyer_notes (internas) NUNCA.
    * Solo se muestran motivos (portal_reason) y los avisos anteriores.
    * Botón Eliminar SOLO si portal_state not in ('in_review','approved').
    * Form Subir/Subir otro SOLO si portal_state in ('pending','rejected','optional').
    * Botón Descargar siempre que haya attachment.
  REGLA "aprobado = solo ver": se aplica en el template Y en el controlador (un
  POST directo a delete/upload sobre un doc aprobado/en revisión debe rechazarse).

================= 7. ENLACE DE ACCESO EN EL PORTAL (TRAMPA) =================
El módulo pyxel_import_website_interface (priority=1000) REEMPLAZA
(position="replace") el bloque portal_common_category del home del portal
(views/components/portal_home.xml). Si pones el enlace en pyxel_import_website lo
pisa y NO aparece. El enlace va EN ESE módulo:
- tarjeta (portal.portal_docs_entry) en portal_common_category con
  t-if="accreditation_count", título "Mi acreditación", url '/my/acreditacion'.
- opcional: <a t-if="accreditation_count" href="/my/acreditacion"> en el menú
  lateral del template ceimpex_portal_side_content_inherit.
Actualizar ese módulo aparte: --update=pyxel_import_website_interface.

================= 9. CAPTURA POR CÁMARA EN LAS 3 VISTAS / MULTI-PÁGINA =================
Permite al cliente subir documentos tomando fotos (móvil o laptop) sin escáner.
Cada foto es una "página"; el sistema arma 1 PDF y lo mete al MISMO flujo (no es
un sistema aparte). El cliente nunca maneja PDFs.

MODELO NUEVO pyxel.lead.document.page (en lead_document.py):
- document_id Many2one('pyxel.lead.document', ondelete='cascade', required, index)
- page_number Integer(default=1) ; image Binary(attachment=True) ; image_filename Char
- quality_score Float (lo fijará el validador, opcional)
En pyxel.lead.document añadir:
- source_type Selection([('file','Archivo subido'),('camera','Foto / cámara')])
- page_ids One2many('pyxel.lead.document.page','document_id')
- page_count Integer(compute) = len(page_ids)
- Método assemble_pdf_from_pages(): con Pillow (ya viene en Odoo) junta las
  page_ids ordenadas por page_number en UN PDF (Image.convert('RGB');
  images[0].save(buf, format='PDF', save_all=True, append_images=images[1:])),
  borra el attachment anterior si existía, crea el ir.attachment (res.partner/
  lead.partner_id.id), y write(attachment_id, upload_date=now, source_type='camera',
  ai_state='validating'). Dejar # TODO del validador IA.
- En build_expediente, marcar source_type='file' a los que llegan con archivo.

SEGURIDAD: en ir.model.access.csv dar acceso a model_pyxel_lead_document_page
para base.group_user (1,1,1,1) y base.group_portal (1,1,1,1).

ENDPOINTS (portal_controller.py):
- /my/acreditacion/page/add/<int:doc_id> (POST, csrf=False): recibe post['image']
  (FileStorage), SOLO si portal_state in ('pending','rejected','optional'); crea una
  page con page_number = max(existentes)+1; responde JSON {"ok":true,"pages":N}.
- /my/acreditacion/page/delete/<int:page_id> (POST): borra una página antes de
  finalizar (validando que el doc sea del usuario y editable).
- /my/acreditacion/finalize/<int:doc_id> (POST): si hay page_ids y estado editable,
  llama assemble_pdf_from_pages().
- IMPORTANTE: en el delete del documento, además de resetear estados, borrar
  doc.page_ids y source_type.

LA CÁMARA VA EN LAS 3 VISTAS. Cada una con su técnica (el documento no siempre
existe aún, por eso difieren):

--- VISTA 2: Portal "Mi acreditación" (el documento YA existe) ---
- JS pyxel_import_website/static/src/js/accreditation_camera.js (vanilla),
  en web.assets_frontend. getUserMedia facingMode {ideal:'environment'}, captura a
  <canvas>, canvas.toBlob -> fetch POST multipart a page/add; botón Listo recarga.
  Listeners delegados (.js-cam-open, #cam_shoot, #cam_cancel, #cam_done).
- Template portal_my_accreditation: por documento editable, botón "📷 Tomar foto"
  (.js-cam-open, data-doc-id, data-doc-label) + form "📁 Subir archivo". Si
  doc.page_ids: miniaturas + "Añadir página" + form finalize + ✕ por página
  (page/delete). Overlay único #cam_overlay (position:fixed) fuera del t-foreach.
  Usa los endpoints page/add, page/delete, finalize de arriba.

--- VISTA 1: Formulario de acreditación (el documento NO existe aún) ---
Como el lead se crea al enviar el form, NO hay endpoint por documento. Solución:
armar el PDF EN EL NAVEGADOR y meterlo en el <input type=file> que el form ya envía.
- jsPDF por CDN en web.assets_frontend:
  https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js
- JS nuevo pyxel_import_website/static/src/js/accreditation_form_camera.js (vanilla,
  AISLADO — NO tocar business_registration.js ni su validación). Inserta un botón
  "📷 Tomar foto" junto a cada input[type=file][name^="doc_"]; al capturar, arma 1
  PDF con jsPDF (new jspdf.jsPDF, addImage ajustando a A4) y lo inyecta en el input:
  DataTransfer -> input.files = dt.files; input.fileList = dt (Odoo usa fileList);
  input.dataset.prevCount="1"; dispatchEvent('change') para que la validación
  existente lo procese. Crea su propio overlay (#accf_cam_overlay) inyectado al body.

--- VISTA 3: Backend, ficha de revisión (reemplazo por el revisor) ---
El revisor (abogada/comercial) puede REEMPLAZAR el documento con foto o archivo.
Campos en pyxel.lead.document: replace_file Binary, replace_filename Char.
Método action_replace_document(): crea attachment desde replace_file, lo asigna,
limpia replace_file, y RE-DISPARA validación (ai_state='validating', resetea
lawyer/commercial) -> el doc vuelve a pasar por la IA. message_post en el lead para
auditoría ("El revisor X reemplazó el documento Y").
- Widget OWL (assets_backend) porque el backend usa OWL, no JS vanilla:
  * jsPDF por CDN en web.assets_backend (mismo URL).
  * pyxel_import_backend/static/src/js/camera_field.js: Component OWL
    'CameraCaptureField' con standardFieldProps; botones "Tomar foto" (getUserMedia
    + <video> + canvas, multi-página) y "Subir archivo" (input file image/pdf).
    Ambos arman PDF con jsPDF y hacen this.props.record.update({[name]: base64,
    replace_filename: '...'}). registry.category("fields").add("camera_capture",
    {component, supportedTypes:["binary"]}).
  * pyxel_import_backend/static/src/xml/camera_field.xml: template OWL
    'pyxel_import.CameraCaptureField' (botones + overlay fixed con video/canvas).
  * En la ficha: <field name="replace_file" widget="camera_capture"/> + botón
    action_replace_document "Aplicar reemplazo".

TRAMPA CÁMARA: getUserMedia solo funciona en localhost o HTTPS. En producción TODO
el sitio (portal y backend) debe estar en HTTPS o la cámara no abre (cae a archivo).

================= 10. ARQUITECTURA DE DOS IA (hooks marcados) =================
Son DOS validadores con responsabilidades distintas; los puntos de integración
están marcados en el código con etiquetas:

A) IA-CALIDAD — valida FOTO A FOTO, en el momento de capturar.
   - Hook: controlador, endpoint /my/acreditacion/page/add (# TODO [IA-CALIDAD]).
   - Entrada: la imagen recién subida. Salida: fijar page.quality_score (0-100) y,
     si la calidad es baja (borrosa/oscura/cortada), devolver
     {"ok": false, "reason": "..."} para que el cliente repita ESA foto antes de
     ensamblar. El JS de cámara ya espera la respuesta JSON.
   - Campo destino: pyxel.lead.document.page.quality_score.

B) IA-DOCUMENTO — valida el PDF COMPLETO ya ensamblado.
   - Hooks (3 puntos, todos marcados # TODO [IA-DOCUMENTO]):
     * assemble_pdf_from_pages() en el modelo (tras armar el PDF de las fotos)
     * upload de archivo PDF directo (portal_controller)
     * action_replace_document() (reemplazo por el revisor; ya re-dispara validación)
   - Entrada: el attachment PDF. Salida: fijar en pyxel.lead.document:
     ai_state (passed/doubt/rejected), ai_confidence (%), ai_quality (%),
     ai_reason (texto) y ai_extracted_data (OCR: NIT, nombre, vencimiento, etc.).
   - Reglas ya implementadas: ai_state='passed' desbloquea a la abogada
     (write override); 'doubt'/'rejected' => el cliente debe resubir.
   Mientras la IA-DOCUMENTO no esté conectada, el documento se queda en
   'validating' (no avanza solo). Para demos, fijar ai_state a mano por odoo shell.

================= 8. NOTAS / TRAMPAS =================
- "Cliente extranjero" no tiene catálogo de documentos (solo Mipyme/Sucursal/
  Estatal/CNA/Proveedor extranjero generan expediente). Añadir a DOC_CATALOG si se necesita.
- Roles: por ahora abogada y comercial usan el mismo grupo (base.group_user).
  Si se requieren permisos separados, crear dos grupos y filtrar botones/registros.
- Comandos: --update=pyxel_import_backend,pyxel_import_website --stop-after-init;
  el módulo interface se actualiza por separado.
- Tras actualizar: reiniciar Odoo y Ctrl+F5 (assets y navbar del portal se cachean).
- El previsualizador muestra PDFs reales; con PDFs de prueba inválidos el visor
  falla pero el resto funciona.
- Para datos de demo usar odoo shell y escribir los 3 estados juntos en cada write
  (evita que el override write toque lawyer_state).
