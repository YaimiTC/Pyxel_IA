# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class Stage(models.Model):
    _inherit = "crm.stage"

    def _default_sequence(self):
        greatest_sequence = self.search([], order='sequence desc', limit=1).sequence
        return greatest_sequence + 1

    is_accreditation_stage = fields.Boolean(string="Is Accreditation Stage?")
    is_rejection_stage = fields.Boolean(string="Is Cancellation Stage?")

    sequence = fields.Integer(default=_default_sequence)

    @api.constrains('is_accreditation_stage', 'is_rejection_stage')
    def _check_accreditation_stage(self):
        for record in self:
            if record.is_accreditation_stage:
                accreditation_stage = self.search([('is_accreditation_stage', '=', True,), ('id', '!=', record.id)], limit=1)
                if accreditation_stage:
                    raise ValidationError(
                        _('There can only be one accreditation stage. '
                          'Record "%s" is already set as accreditation stage.') % accreditation_stage.name
                    )
                
            if record.is_rejection_stage:
                rejection_stage = self.search([('is_rejection_stage', '=', True), ('id', '!=', record.id)], limit=1)
                if rejection_stage:
                    raise ValidationError(
                        _('There can only be one cancellation stage. '
                          'Record "%s" is already set as cancellation stage.') % rejection_stage.name
                    )

    # Si se cambia de True a False cualquiera de estos campos ['is_accreditation_stage', 'is_rejection_stage', 'is_won'] 
    # y se pone otro en True, entonces el campo cambiado a False no
    # cambia realmente, porque estará en readonly en la vista y no se envía a este método write
    def write(self, vals):
        if 'is_accreditation_stage' in vals and vals['is_accreditation_stage']:
            vals['is_rejection_stage'] = False
            vals['is_won'] = False
        elif 'is_rejection_stage' in vals and vals['is_rejection_stage']:
            vals['is_accreditation_stage'] = False
            vals['is_won'] = False
        elif 'is_won' in vals and vals['is_won']:
            vals['is_accreditation_stage'] = False
            vals['is_rejection_stage'] = False
        return super(Stage, self).write(vals)
