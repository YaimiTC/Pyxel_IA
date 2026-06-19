from odoo import models, api, _
import logging

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def action_post(self):
        # Llama al método original de Odoo para publicar el pago.
        res = super().action_post()

        for payment_id in self.ids:
            # Recarga el objeto 'payment' para asegurar que tiene los datos más recientes.
            payment = self.env['account.payment'].browse(payment_id)

            _logger.info(f"Procesando pago: {payment.name} (ID: {payment.id}) para notificación de correo y chatters.")

            # Asegúrate de que el pago está en estado 'posted' antes de intentar enviar el correo.
            if payment.state != 'posted':
                _logger.warning(f"El pago {payment.name} no está en estado 'posted'. Saltando notificación.")
                continue

            # Solo proceder si el pago tiene un partner (cliente/proveedor) y un correo electrónico.
            if payment.partner_id.contact_type_id.type_of_contact == "Supplier" and payment.partner_id.email:

                template = self.env.ref('pyxel_import_backend.email_template_payment_registered',
                                        raise_if_not_found=False)

                if template:
                    try:
                        # Envía el correo electrónico al partner del pago.
                        template.send_mail(payment.id, force_send=True)

                        # --- CLAVE: Registrar en el CHATTER del PAGO ---
                        payment.message_post(
                            subject="Correo de Notificación de Pago Enviado",
                            body=f"Se envió un correo electrónico al proveedor **{payment.partner_id.name}** "
                                 f"({payment.partner_id.email}) notificando el registro de este pago."
                        )
                        _logger.info(f"Mensaje en chatter del pago para {payment.name}.")

                        # --- CLAVE: Registrar en el CHATTER del PARTNER ---
                        payment.partner_id.message_post(
                            subject=f"Pago Registrado: {payment.name}",
                            body=f"Se ha registrado un pago por **{payment.amount:.2f} {payment.currency_id.symbol}** "
                                 f"a su favor (o de su empresa). "
                                 f"Se envió una notificación por correo electrónico."
                        )
                        _logger.info(
                            f"Mensaje en chatter del partner {payment.partner_id.name} para el pago {payment.name}.")

                    except Exception as e:
                        # Si ocurre un error al enviar el correo, registrarlo en el chatter del pago y del partner.
                        error_msg = f"Hubo un error al intentar enviar el correo de notificación al partner " \
                                    f"**{payment.partner_id.name}** ({payment.partner_id.email}). Error: {e}"
                        payment.message_post(
                            subject="Error al Enviar Correo de Notificación de Pago",
                            body=error_msg
                        )
                        if payment.partner_id:  # Asegurarse de que el partner existe antes de intentar postear
                            payment.partner_id.message_post(
                                subject="Error en Notificación de Pago",
                                body=f"Hubo un error al intentar enviar el correo de notificación para el pago {payment.name}. Por favor, revise el pago."
                            )
                        _logger.error(f"Error al enviar correo para pago {payment.name}: {e}")
                else:
                    # Si la plantilla de correo no se encuentra, registrarlo en el chatter del pago y del partner.
                    template_error_msg = f"No se pudo enviar el correo de notificación de pago al partner " \
                                         f"**{payment.partner_id.name}** porque la plantilla de correo " \
                                         f"'pyxel_import_backend.email_template_payment_registered' no fue encontrada."
                    payment.message_post(
                        subject="Error: Plantilla de Correo No Encontrada",
                        body=template_error_msg
                    )
                    if payment.partner_id:  # Asegurarse de que el partner existe antes de intentar postear
                        payment.partner_id.message_post(
                            subject="Error en Notificación de Pago",
                            body=f"No se encontró la plantilla de correo para el pago {payment.name}. Por favor, revise la configuración."
                        )
                    _logger.warning(f"Plantilla de correo no encontrada para el pago {payment.name}.")
            else:
                # Si no hay partner o no hay email, registrarlo en el chatter del pago.
                reason = "no tiene partner asociado" if not payment.partner_id else "el partner no tiene correo electrónico"
                payment.message_post(
                    subject="Correo de Notificación No Enviado",
                    body=f"No se envió correo de notificación para este pago porque {reason}."
                )
                _logger.info(f"No se envió correo para el pago {payment.name}: {reason}.")

        return res