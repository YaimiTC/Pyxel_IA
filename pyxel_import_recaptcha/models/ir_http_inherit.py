import logging
import requests
from odoo import api, models, _

_logger = logging.getLogger(__name__)


class Http(models.AbstractModel):
    _inherit = 'ir.http'

    def _verify_request_recaptcha_token(self, action):
        included_actions = ["login", "reset_password", "signup"]
        _logger.info("action!!!" + str(action))
        if action in included_actions:
            _logger.info("incluyo!!!" + str(action))
            return super()._verify_request_recaptcha_token(action)

        _logger.info("continuo!!!!!" + str(action))
        return True




