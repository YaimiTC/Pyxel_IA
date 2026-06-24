from odoo import models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def write(self, vals):
        res = super().write(vals)
        if vals.get('stage_id'):
            new_stage = self.env['crm.stage'].browse(vals['stage_id'])
            if new_stage.is_accreditation_stage and not new_stage.is_rejection_stage:
                for lead in self:
                    self._notify_accredited(lead)
        return res

    def _notify_accredited(self, lead):
        partner = lead.partner_id
        phone = partner.whatsapp_phone or partner.mobile or partner.phone
        if not phone:
            return
        msg = (
            f"✅ *ENETRADEX* — Acreditación aprobada\n\n"
            f"Estimado/a {partner.name},\n\n"
            f"Su empresa ha sido *acreditada exitosamente* en la plataforma ENETRADEX.\n\n"
            f"Ya puede acceder a todas las funcionalidades del portal:\n"
            f"🔗 https://enetradex.com/my\n\n"
            f"📞 +53 5280 7765 | comercial@enetec.telmark.com.cu"
        )
        self.env['whatsapp.service'].send(phone, msg)
