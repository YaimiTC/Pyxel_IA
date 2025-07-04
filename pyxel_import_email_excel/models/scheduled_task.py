from datetime import datetime, time, timedelta

from odoo import models, fields, api


class ScheduledTask(models.Model):
    _name = 'scheduled.task'
    _description = 'Scheduled Task'

    name = fields.Char(string='Name')

    @api.model
    def scheduled_check_import_errors(self):
        now = datetime.now()
        start_time = datetime.combine(now.date(), time.min)
        end_time = datetime.combine(now.date(), time(8, 0))

        error_logs = self.env['import.error.log'].search(
            [('import_date', '>=', start_time), ('import_date', '<=', end_time)])

        valid_email_received = any(log.name == 'Correo recibido con adjunto valido' for log in error_logs)
        if not valid_email_received:
            incorrect_format_email = any(
                log.name == 'Correo recibido con adjunto en un formato incorrecto' for log in error_logs)
            message = 'No se recibió el correo.' if not incorrect_format_email else 'El correo entró pero el adjunto no tiene el formato requerido para su procesamiento.'

            notification_emails = self.env['ir.config_parameter'].sudo().get_param('notification_emails')
            mail_server_id = self.env['ir.config_parameter'].sudo().get_param('outgoing_mail_server_id')

            if notification_emails and mail_server_id:
                email_list = notification_emails.split(',')
                mail_server = self.env['ir.mail_server'].browse(int(mail_server_id))
                email_from = mail_server.smtp_user

                mail_values = {
                    'subject': 'Informe sobre el Adjunto de la TCM',
                    'body_html': message,
                    'email_to': ','.join(email_list),
                    'email_from': email_from,
                    'mail_server_id': int(mail_server_id),
                }
                self.env['mail.mail'].create(mail_values).send()

    @api.model
    def scheduled_check_contract_expiration(self):
        now = datetime.now()
        days_before_expiration = int(
            self.env['ir.config_parameter'].sudo().get_param('days_until_expiration', default=0))
        expiration_date = now + timedelta(days=days_before_expiration)

        active_contracts = self.env['res.partner.contract.import'].search([
            ('active_contract', '=', True),
            ('end_date', '<=', expiration_date)
        ])

        salespersons_emails = self.env['ir.config_parameter'].sudo().get_param('salespersons_emails')
        mail_server_id = self.env['ir.config_parameter'].sudo().get_param('contract_outgoing_mail_server_id')

        if salespersons_emails and mail_server_id:
            email_list = salespersons_emails.split(',')
            mail_server = self.env['ir.mail_server'].browse(int(mail_server_id))
            email_from = mail_server.smtp_user

            for contract in active_contracts:
                partner_email = contract.partner_id.email or False
                contract_name = contract.name
                if partner_email:
                    message = f'El contrato ({contract_name}) firmado con Frutas Selectas se encuentra próximo a vencerse, se le enviará el suplemento para la continuidad de los servicios con nosotros'
                    mail_values = {
                        'subject': 'Notificación de expiración del contrato',
                        'body_html': message,
                        'email_to': partner_email,
                        'email_cc': ','.join(email_list),
                        'email_from': email_from,
                        'mail_server_id': int(mail_server_id),
                    }
                else:
                    message = f'El contrato ({contract_name}) se encuentra próximo a vencerse, pero no puedo notificar al cliente hasta que usted le agregue una dirección de correo electrónico.'
                    mail_values = {
                        'subject': 'Notificación de expiración del contrato',
                        'body_html': message,
                        'email_to': ','.join(email_list),
                        'email_from': email_from,
                        'mail_server_id': int(mail_server_id),
                    }
                self.env['mail.mail'].create(mail_values).send()

    @api.model
    def scheduled_check_containers_status(self):
        now = fields.Datetime.now()

        active_containers = self.env['importation.load'].search([
            ('return_date', '=', False)])

        salespersons_emails = self.env['ir.config_parameter'].sudo().get_param('containers_salespersons_emails')
        mail_server_id = self.env['ir.config_parameter'].sudo().get_param('containers_outgoing_mail_server_id')

        if salespersons_emails and mail_server_id:
            email_list = salespersons_emails.split(',')
            mail_server = self.env['ir.mail_server'].browse(int(mail_server_id))
            email_from = mail_server.smtp_user

            for container in active_containers:
                import_order = container.importation_id
                purchase_orders = import_order.purchase_ids
                purchase_order = purchase_orders.sorted(key=lambda o: o.id)[0] if purchase_orders else None
                customer = purchase_order.sale_order_id.partner_id if purchase_order and purchase_order.sale_order_id else None
                salesperson = purchase_order.user_id.partner_id if (purchase_order and purchase_order.user_id) else None
                container_name = container.name
                import_request_name = container.importation_id.name
                if not purchase_orders:
                    message = f'La solicitud de importación {import_request_name} relativa al contenedor ({container_name}) No tiene asociada ninguna orden de compra.'
                    mail_values = {
                        'subject': f'Problemas con las órdenes de compra. Contenedor: {container_name}. Solicitud de importación: {import_request_name}',
                        'body_html': message,
                        'email_to': ','.join(email_list),
                        'email_from': email_from,
                        'mail_server_id': int(mail_server_id),
                    }
                    self.env['mail.mail'].create(mail_values).send()
                    continue
                elif not customer and not salesperson:
                    message = f'La solicitud de importación {import_request_name} relativa al contenedor ({container_name}) No tiene asociado ni cliente ni comercial.'
                    mail_values = {
                        'subject': f'Problemas con el cliente y el comercial. Contenedor: {container_name}. Solicitud de importación: {import_request_name}',
                        'body_html': message,
                        'email_to': ','.join(email_list),
                        'email_from': email_from,
                        'mail_server_id': int(mail_server_id),
                    }
                    self.env['mail.mail'].create(mail_values).send()
                    continue
                elif not salesperson:
                    message = f'Problemas con el comercial. Contenedor: {container_name}. Solicitud de importación: {import_request_name}'
                    mail_values = {
                        'subject': f'Problemas en la solicitud de importación {import_request_name}',
                        'body_html': message,
                        'email_to': ','.join(email_list),
                        'email_from': email_from,
                        'mail_server_id': int(mail_server_id),
                    }
                    self.env['mail.mail'].create(mail_values).send()
                    continue
                elif not salesperson.email:
                    message = f'El comercial {salesperson.name} no puede ser notificado hasta que usted le agregue una dirección de correo electrónico.'
                    mail_values = {
                        'subject': f'Problemas con el comercial. Contenedor: {container_name}. Solicitud de importación: {import_request_name}',
                        'body_html': message,
                        'email_to': ','.join(email_list),
                        'email_from': email_from,
                        'mail_server_id': int(mail_server_id),
                    }
                    self.env['mail.mail'].create(mail_values).send()
                    continue
                elif not customer:
                    message = f'La solicitud de importación {import_request_name} relativa al contenedor ({container_name}) No tiene asociado un cliente.'
                    mail_values = {
                        'subject': f'Problemas con el cliente. Contenedor: {container_name}. Solicitud de importación: {import_request_name}',
                        'body_html': message,
                        'email_to': salesperson.email,
                        'email_cc': ','.join(email_list),
                        'email_from': email_from,
                        'mail_server_id': int(mail_server_id),
                    }
                    self.env['mail.mail'].create(mail_values).send()
                    continue
                elif not customer.email:
                    message = f'El cliente ({customer.name}) no puede ser notificado hasta que usted le agregue una dirección de correo electrónico.'
                    mail_values = {
                        'subject': f'Problemas con el cliente. Contenedor: {container_name}. Solicitud de importación: {import_request_name}',
                        'body_html': message,
                        'email_to': salesperson.email,
                        'email_cc': ','.join(email_list),
                        'email_from': email_from,
                        'mail_server_id': int(mail_server_id),
                    }
                    self.env['mail.mail'].create(mail_values).send()
                    continue
                else:
                    if container.state == 'to_extract':
                        message = f'El contenedor ({container_name}) se encuentra liberado y aún no ha sido extraído. Comenzará a pagar gastos asociados a la demora.'
                        mail_values = {
                            'subject': f'Contenedor {container_name} listo para su extracción',
                            'body_html': message,
                            'email_to': customer.email,
                            'email_cc': salesperson.email,
                            'email_bcc': ','.join(email_list),
                            'email_from': email_from,
                            'mail_server_id': int(mail_server_id),
                        }
                        self.env['mail.mail'].create(mail_values).send()
                        continue
                    if container.state == 'to_return':
                        extraction_date = fields.Datetime.from_string(container.extraction_date)
                        time_diff = now - extraction_date
                        if time_diff.total_seconds() >= 24 * 3600:
                            message = f'El contenedor ({container_name}) aún no se encuentra devuelto.'
                            mail_values = {
                                'subject': f'Devolución del contenedor {container_name}',
                                'body_html': message,
                                'email_to': customer.email,
                                'email_cc': salesperson.email,
                                'email_bcc': ','.join(email_list),
                                'email_from': email_from,
                                'mail_server_id': int(mail_server_id),
                            }
                            self.env['mail.mail'].create(mail_values).send()
