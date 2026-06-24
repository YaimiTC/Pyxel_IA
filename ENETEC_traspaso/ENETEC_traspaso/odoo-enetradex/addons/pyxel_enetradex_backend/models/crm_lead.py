from markupsafe import Markup

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools import html_escape as _esc


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # ENETRADEX (Fase 0): chip Cliente/Proveedor para la bandeja única del abogado.
    # Se deriva del tipo de contacto del partner (type_of_contact: Client/Supplier),
    # que ya existe en res.partner.contact.type. Almacenado e indexado para
    # poder filtrar y agrupar por tipo en el kanban/lista del CRM.
    en_party_role = fields.Selection(
        [('client', 'Cliente'), ('supplier', 'Proveedor')],
        string="Tipo de empresa", store=True, index=True,
        compute='_compute_en_party_role',
    )

    # ENETRADEX: quién originó esta acreditación. 'self' = la propia empresa;
    # 'counterparty' = la inició una contraparte (sub-acreditación: subir info / invitar).
    en_initiated_by = fields.Selection(
        [('self', 'Propia'), ('counterparty', 'Por contraparte')],
        string="Acreditación iniciada por", default='self')
    en_inviter_partner_id = fields.Many2one('res.partner', string="Invitado/registrado por")

    # Datos de acreditación traídos del partner (para que el abogado los vea en el lead).
    en_partner_ctype = fields.Many2one('res.partner.contact.type', related='partner_id.contact_type_id',
                                       string="Tipo de contacto", readonly=True)
    en_partner_mtype = fields.Many2one('res.partner.management.type', related='partner_id.management_type_id',
                                       string="Naturaleza de la empresa", readonly=True)
    en_partner_vat = fields.Char(related='partner_id.vat', string="NIT", readonly=True)
    en_partner_objeto = fields.Text(related='partner_id.objeto_social', string="Objeto social", readonly=True)
    en_partner_accredited = fields.Boolean(related='partner_id.is_accredited', string="Empresa acreditada", readonly=True)

    # Documentos subidos en el wizard (adjuntos del propio lead), mostrados como tarjetas.
    en_document_ids = fields.Many2many('ir.attachment', string="Documentos de acreditación",
                                       compute='_compute_en_document_ids')

    def _compute_en_document_ids(self):
        Att = self.env['ir.attachment']
        for lead in self:
            rid = lead.id or lead._origin.id
            lead.en_document_ids = Att.search([('res_model', '=', 'crm.lead'), ('res_id', '=', rid)]) if rid else Att

    # ENETRADEX: recorrido de acreditación con la misma estética del portal (clases
    # .en-track, estilizadas en agrimpex_backend.scss). Banner acreditado/pendiente
    # + línea de tiempo de eventos del lead.
    en_tracking_ids = fields.One2many('en.tracking.event', 'lead_id', string="Eventos de seguimiento")

    # Tipo de entidad para el expediente (seleccionable si no se puede inferir del partner)
    accreditation_client_type = fields.Selection([
        ('Pymes', 'Pyme'),
        ('Estatal', 'Estatal'),
        ('CNA', 'CNA'),
        ('Sucursal Extranjera', 'Sucursal Extranjera'),
        ('Proveedor', 'Proveedor'),
    ], string="Tipo de entidad")

    # Expediente de acreditación (validación de 3 pasos por documento)
    accreditation_document_ids = fields.One2many('pyxel.lead.document', 'lead_id',
                                                 string="Documentación de acreditación")
    accreditation_doc_count = fields.Integer(string="Documentos requeridos", compute='_compute_accreditation_counts')
    accreditation_approved_count = fields.Integer(string="Aprobados", compute='_compute_accreditation_counts')
    accreditation_review_count = fields.Integer(string="En revisión", compute='_compute_accreditation_counts')
    accreditation_pending_count = fields.Integer(string="Pendientes", compute='_compute_accreditation_counts')

    @api.depends('accreditation_document_ids.portal_state', 'accreditation_document_ids.is_required')
    def _compute_accreditation_counts(self):
        for lead in self:
            req = lead.accreditation_document_ids.filtered(lambda d: d.is_required)
            lead.accreditation_doc_count = len(req)
            lead.accreditation_approved_count = len(
                req.filtered(lambda d: d.portal_state == 'approved'))
            lead.accreditation_review_count = len(
                req.filtered(lambda d: d.portal_state in ('in_review', 'validating')))
            lead.accreditation_pending_count = len(
                req.filtered(lambda d: d.portal_state in ('pending', 'rejected')))

    def _try_accredit_from_expediente(self):
        """Cuando TODOS los documentos requeridos del expediente quedan aprobados,
        mueve el lead a la etapa de acreditación (is_accreditation_stage) -> la
        empresa queda is_accredited y ya no se le pide acreditarse de nuevo."""
        stage = self.env['crm.stage'].sudo().search(
            [('is_accreditation_stage', '=', True), ('is_rejection_stage', '=', False)],
            order='sequence', limit=1)
        if not stage:
            return
        for lead in self:
            req = lead.accreditation_document_ids.filtered(lambda c: c.is_required)
            if req and all(d.portal_state == 'approved' for d in req) and lead.stage_id.id != stage.id:
                lead.with_context(en_skip_expediente_gate=True, en_auto_event=True).stage_id = stage.id

    def action_generate_expediente(self):
        """Genera el expediente de acreditación para leads existentes que no lo tienen."""
        self.ensure_one()
        if self.accreditation_document_ids:
            raise ValidationError(_("Este lead ya tiene un expediente generado."))
        if not self.partner_id:
            raise ValidationError(_("El lead no tiene empresa asociada. Asígnala antes de generar el expediente."))
        if not self.accreditation_client_type:
            raise ValidationError(_("Selecciona el Tipo de entidad antes de generar el expediente."))
        attachments = self.env['ir.attachment'].search([
            ('res_model', '=', 'crm.lead'), ('res_id', '=', self.id)])
        uploaded = {att.name.replace('.pdf', '').replace('.jpg', '').replace('.png', ''): att.id
                    for att in attachments}
        self.env['pyxel.lead.document'].sudo().build_expediente(self, self.accreditation_client_type, uploaded)
        return True

    def _check_expediente_complete(self):
        """Gate: no se puede acreditar hasta que el expediente esté aprobado."""
        for lead in self:
            req = lead.accreditation_document_ids.filtered(lambda d: d.is_required)
            pend = req.filtered(lambda d: d.portal_state != 'approved')
            if req and pend:
                raise ValidationError(_(
                    "No se puede acreditar «%(name)s»: el expediente aún no está "
                    "aprobado. Faltan %(n)s documento(s): %(labels)s.") % {
                        'name': lead.name or '',
                        'n': len(pend),
                        'labels': ', '.join(pend.mapped('document_label')),
                    })
    en_timeline_html = fields.Html(string="Recorrido de acreditación", sanitize=False,
                                   compute='_compute_en_timeline_html')
    # Estado de acreditación como selección (para badge en kanban/lista).
    en_accred_state = fields.Selection(
        [('accredited', 'Acreditado'), ('pending', 'Pendiente')],
        string="Estado de acreditación", compute='_compute_en_accred_state', store=False)

    @api.depends('partner_id.is_accredited')
    def _compute_en_accred_state(self):
        for lead in self:
            lead.en_accred_state = 'accredited' if lead.partner_id.is_accredited else 'pending'

    # Diferenciación cliente/proveedor + vínculo entre las dos acreditaciones de
    # una misma solicitud (empresa que se acredita + contraparte que registró).
    en_doc_count = fields.Integer(string="Documentos", compute='_compute_en_doc_count')
    en_origin_label = fields.Char(string="Origen", compute='_compute_en_links')
    en_also_registered = fields.Char(string="También registró", compute='_compute_en_links')

    @api.depends('en_document_ids')
    def _compute_en_doc_count(self):
        for lead in self:
            lead.en_doc_count = len(lead.en_document_ids)

    @api.depends('en_initiated_by', 'en_inviter_partner_id', 'partner_id')
    def _compute_en_links(self):
        Lead = self.env['crm.lead']
        for lead in self:
            if lead.en_initiated_by == 'counterparty' and lead.en_inviter_partner_id:
                lead.en_origin_label = "Registrado por %s" % lead.en_inviter_partner_id.name
            else:
                lead.en_origin_label = "Acreditación propia"
            others = Lead.search([
                ('en_inviter_partner_id', '=', lead.partner_id.id),
                ('id', '!=', lead._origin.id or lead.id)]) if lead.partner_id else Lead
            lead.en_also_registered = ', '.join(others.mapped('partner_id.name')) or False

    @api.depends('partner_id', 'partner_id.is_accredited', 'partner_id.vat',
                 'partner_id.objeto_social', 'stage_id', 'en_party_role', 'en_tracking_ids',
                 'en_tracking_ids.stage_name', 'en_tracking_ids.date')
    def _compute_en_timeline_html(self):
        stages = self.env['crm.stage'].sudo().search([], order='sequence')
        role_sel = dict(self._fields['en_party_role'].selection)
        for lead in self:
            partner = lead.partner_id
            accredited = bool(partner.is_accredited)
            cls = 'success' if accredited else 'warning'
            icon = 'fa-check' if accredited else 'fa-clock-o'
            txt = "Empresa acreditada" if accredited else "Acreditación en proceso"
            h = '<div class="en-track en-track-backend">'
            # Banner de estado
            h += ('<div class="en-action %s"><span class="ico"><i class="fa %s"></i></span>'
                  '<span>%s — %s</span></div>') % (cls, icon, _esc(partner.name or ''), txt)
            # Pipeline de etapas de acreditación (resaltando la actual)
            cur = lead.stage_id
            h += '<div class="en-pipeline">'
            for st in stages:
                state = 'done' if (cur and st.sequence < cur.sequence) else ('cur' if cur and st.id == cur.id else '')
                h += ('<div class="pstep %s"><span class="pdot"></span>'
                      '<span class="pname">%s</span></div>') % (state, _esc(st.name or ''))
            h += '</div>'
            # Datos de la empresa
            kv = [
                ("Tipo", role_sel.get(lead.en_party_role) or '—'),
                ("NIT", partner.vat or '—'),
                ("Naturaleza", partner.management_type_id.name or '—'),
                ("Tipo de contacto", partner.contact_type_id.name or '—'),
                ("Dirección", ', '.join(
                    x for x in [partner.street, partner.city, partner.state_id.name] if x) or '—'),
            ]
            h += '<div class="en-card"><h4>Datos de la empresa</h4><div class="en-kv">'
            for k, v in kv:
                h += '<div><span class="k">%s</span><span class="v">%s</span></div>' % (k, _esc(v))
            h += '</div>'
            if partner.objeto_social:
                h += ('<div class="en-kv-full"><span class="k">Objeto social</span>'
                      '<span class="v">%s</span></div>') % _esc(partner.objeto_social)
            contact = partner.child_ids[:1]
            if contact:
                cinfo = contact.name or ''
                extra = [x for x in (contact.email, contact.phone) if x]
                if extra:
                    cinfo += ' · ' + ' · '.join(extra)
                h += ('<div class="en-kv-full"><span class="k">Persona de contacto</span>'
                      '<span class="v">%s</span></div>') % _esc(cinfo)
            h += '</div>'
            # Vínculo entre las dos acreditaciones de una misma solicitud
            link_html = ''
            if lead.en_initiated_by == 'counterparty' and lead.en_inviter_partner_id:
                link_html += ('<div class="en-link"><i class="fa fa-sign-in"></i> Acreditación '
                              '<b>registrada por %s</b> (acreditación propia + contraparte).</div>'
                              ) % _esc(lead.en_inviter_partner_id.name)
            others = self.env['crm.lead'].search(
                [('en_inviter_partner_id', '=', partner.id), ('id', '!=', lead.id)]) if partner else self.env['crm.lead']
            for o in others:
                ost = 'Acreditado' if o.partner_id.is_accredited else 'Pendiente'
                link_html += ('<div class="en-link"><i class="fa fa-sitemap"></i> También registró a '
                              '<a href="/web#id=%s&amp;model=crm.lead&amp;view_type=form"><b>%s</b></a> '
                              '<span class="en-tag">%s</span></div>') % (o.id, _esc(o.partner_id.name), ost)
            if link_html:
                h += '<div class="en-card"><h4>Vínculo de acreditación</h4>%s</div>' % link_html
            # Socio(s) cubano(s) residente(s) en el exterior (proveedor extranjero)
            socios = partner.en_cuban_partner_ids
            if socios:
                h += ('<div class="en-card"><h4>Socio de nacionalidad cubana '
                      '(residente en el exterior)</h4>')
                for s in socios:
                    rows = [
                        ("Nombre y apellidos", s.name),
                        ("No. Pasaporte", s.passport_no),
                        ("No. Pasaporte extranjero", s.foreign_passport_no),
                        ("Fecha de nacimiento", s.birth_date),
                        ("Lugar de nacimiento", s.birth_place),
                        ("Padre", s.father_info),
                        ("Madre", s.mother_info),
                        ("Dirección actual", s.current_address),
                        ("Correo / móvil / fijo",
                         ' · '.join(x for x in [s.email, s.mobile, s.landline] if x)),
                        ("Salida de Cuba", s.exit_date),
                        ("Última dirección en Cuba", s.last_address_cuba),
                        ("Graduado de", s.graduated_of),
                        ("Fecha de graduado", s.graduation_date),
                        ("Labor en Cuba", s.work_in_cuba),
                    ]
                    h += '<div class="en-kv">'
                    for k, v in rows:
                        if v:
                            h += ('<div><span class="k">%s</span>'
                                  '<span class="v">%s</span></div>') % (k, _esc(str(v)))
                    h += '</div>'
                h += '</div>'
            # Regla del proceso (texto claro)
            h += ('<div class="en-note"><i class="fa fa-info-circle"></i> La operación de importación '
                  'que une a las dos partes <b>solo avanza cuando ambas están acreditadas</b>. '
                  'Una vez acreditada, esta empresa puede iniciar una <b>nueva operación con otra '
                  'contraparte ya acreditada</b>.</div>')
            # Recorrido de acreditación (línea de tiempo)
            events = lead.en_tracking_ids.sorted(lambda e: (e.date or fields.Datetime.now(), e.id))
            if events:
                h += '<div class="en-card"><h4>Recorrido de acreditación</h4><ul class="en-tl">'
                for ev in events:
                    dot = 'auto' if ev.source == 'auto' else 'manual'
                    src = "Automático" if ev.source == 'auto' else "Comercial"
                    local_dt = fields.Datetime.context_timestamp(ev, ev.date) if ev.date else False
                    date = local_dt.strftime('%d/%m/%Y %H:%M') if local_dt else ''
                    resp = ' · ' + _esc(ev.user_id.name) if (ev.source == 'manual' and ev.user_id) else ''
                    phase_tag = "Acreditación" if ev.phase == 'accreditation' else "Importación"
                    note = '<div class="en-meta">%s</div>' % _esc(ev.note) if ev.note else ''
                    h += ('<li><span class="en-dot %s"></span>'
                          '<div class="en-row"><span class="t-title">%s</span>'
                          '<span class="en-tag">%s</span><span class="en-tag">%s</span></div>'
                          '<div class="en-meta">%s%s</div>%s</li>') % (
                        dot, _esc(ev.stage_name or ev.name or ''), phase_tag, src, date, resp, note)
                h += '</ul></div>'
            h += '</div>'
            lead.en_timeline_html = Markup(h)

    @api.depends('partner_id', 'partner_id.contact_type_id', 'partner_id.contact_type_id.type_of_contact')
    def _compute_en_party_role(self):
        for lead in self:
            t = lead.partner_id.contact_type_id.type_of_contact
            lead.en_party_role = 'client' if t == 'Client' else ('supplier' if t == 'Supplier' else False)

    @api.depends('partner_id')
    def _compute_name(self):
        # Overwrite
        for lead in self:
            if not lead.name and lead.partner_id and lead.partner_id.name:
                lead.name = lead.partner_id.name

    # ENETRADEX: seguimiento — registrar eventos de acreditación para la línea de
    # tiempo que ve el cliente en su cuenta.
    @api.model_create_multi
    def create(self, vals_list):
        leads = super().create(vals_list)
        Ev = self.env['en.tracking.event']
        for lead in leads:
            if lead.en_party_role:  # solo solicitudes de acreditación ENETRADEX
                Ev.en_log_event(
                    lead, 'accreditation', lead.stage_id.name, lead.partner_id,
                    source='auto', event_type='created',
                    note="Solicitud de acreditación recibida.")
        return leads

    def write(self, vals):
        if False and vals.get('stage_id') and not self.env.context.get('en_skip_expediente_gate'):
            new_stage = self.env['crm.stage'].browse(vals['stage_id'])
            if new_stage.is_accreditation_stage:
                self._check_expediente_complete()
        res = super().write(vals)
        if vals.get('stage_id'):
            auto = self.env.context.get('en_auto_event')
            Ev = self.env['en.tracking.event']
            for lead in self:
                if lead.en_party_role:
                    Ev.en_log_event(
                        lead, 'accreditation', lead.stage_id.name, lead.partner_id,
                        source='auto' if auto else 'manual')
            # Al quedar acreditada la empresa, avanzar automáticamente sus
            # operaciones en gate que ya tengan a AMBAS partes acreditadas.
            new_stage = self.env['crm.stage'].browse(vals['stage_id'])
            if new_stage.is_accreditation_stage:
                partners = self.mapped('partner_id')
                partners.invalidate_recordset(['is_accredited'])
                self.env['importation.process']._en_advance_for_partners(partners)
        return res
