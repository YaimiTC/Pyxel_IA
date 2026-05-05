from odoo import models, fields, api
import email
import base64
import logging
import quopri
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class FetchmailServer(models.Model):
    _inherit = 'fetchmail.server'

    def fetch_mail(self):
        # Registrar el error en un log
        log = self.env['import.error.log'].create({
            'name': 'Registro de ejecución de fetchmail',
            'import_date': datetime.now()
        })

        """ WARNING: meant for cron usage only - will commit() after each email! """
        additionnal_context = {
            'fetchmail_cron_running': True
        }
        MailThread = self.env['mail.thread']
        for server in self:
            _logger.info('start checking for new emails on %s server %s', server.server_type, server.name)
            additionnal_context['default_fetchmail_server_id'] = server.id
            count, failed = 0, 0
            imap_server = None
            pop_server = None
            connection_type = server._get_connection_type()
            if connection_type == 'imap':
                try:
                    imap_server = server.connect()
                    imap_server.select()
                    result, data = imap_server.search(None, '(UNSEEN)')
                    email_ids = data[0].split()

                    email_from = self.env['ir.config_parameter'].sudo().get_param('email_from')
                    # email_subject = self.env['ir.config_parameter'].sudo().get_param('email_subject')

                    _logger.info("EL REMITENTE CONFIGURADO ES %s ", email_from, exc_info=True)

                    for email_id in email_ids:
                        res_id = None
                        result, msg_data = imap_server.fetch(email_id, '(RFC822)')
                        msg = email.message_from_bytes(msg_data[0][1])
                        sender = msg['from']
                        subject = msg['subject']

                        # Verificar Configuración
                        self.env['import.error.line'].create({
                            'log_id': log.id,
                            'line_number': '1',
                            'error_message': "{} ES EL REMITENTE CONFIGURADO".format(email_from),
                            'data': "Configuración de remitente correcta"
                        })

                        # Verificar remitente y asunto
                        _logger.info("EL REMITENTE DEL CORREO ES %s Y EL SUJETO ES %s.", sender, subject, exc_info=True)

                        self.env['import.error.line'].create({
                            'log_id': log.id,
                            'line_number': '3',
                            'error_message': "{} ES EL REMITENTE DEL CORREO ENCONTRADO".format(sender),
                            'data': "Se encontró un correo no leido"
                        })

                        self.env['import.error.line'].create({
                            'log_id': log.id,
                            'line_number': '4',
                            'error_message': "{} ES EL ASUNTO DEL CORREO ENCONTRADO".format(subject),
                            'data': "Pasa a la fase de comprobación"
                        })

                        # if email_from in sender and email_subject in subject:
                        if email_from in sender:
                            _logger.info("ENCONTRADO EL CORREO")

                            self.env['import.error.line'].create({
                                'log_id': log.id,
                                'line_number': '5',
                                'error_message': "El correo cumple con los parámetros de configuración",
                                'data': "ENCONTRADO"
                            })

                            for part in msg.walk():
                                _logger.info("TIPO DE CONTENIDO: %s", part.get_content_maintype())
                                _logger.info("DISPOSICIÓN DEL CONTENIDO: %s", part.get('Content-Disposition'))

                                self.env['import.error.line'].create({
                                    'log_id': log.id,
                                    'line_number': '6',
                                    'error_message': "{} ES EL tipo de contenido".format(part.get_content_maintype()),
                                    'data': "Comprobando el contenido"
                                })

                                self.env['import.error.line'].create({
                                    'log_id': log.id,
                                    'line_number': '7',
                                    'error_message': "{} ES la disposicion del contenido".format(
                                        part.get('Content-Disposition')),
                                    'data': "Comprobando la disposicion del contenido"
                                })

                                filename = part.get_filename()
                                if filename:
                                    filename = quopri.decodestring(filename).decode('utf-8')

                                    self.env['import.error.line'].create({
                                        'log_id': log.id,
                                        'line_number': '8',
                                        'error_message': "{} Es el nombre del adjunto".format(filename),
                                        'data': "Adjunto encontrado"
                                    })
                                    log.write({
                                        'name': 'Correo recibido con adjunto en un formato incorrecto'
                                    })

                                if part.get_content_maintype() == 'multipart':
                                    continue
                                # if part.get('Content-Disposition') is None:
                                #     continue
                                if filename and 'csv' in filename:

                                    self.env['import.error.line'].create({
                                        'log_id': log.id,
                                        'line_number': '9',
                                        'error_message': "Comprobación de formato csv".format(filename),
                                        'data': "Tipo de adjunto correcto"
                                    })

                                    attachment_data = part.get_payload(decode=True)
                                    attachment = {
                                        'filename': filename,
                                        'content': base64.b64encode(attachment_data).decode('utf-8')
                                    }
                                    # Llamar a la función para procesar el adjunto
                                    _logger.info("LE PASO EL ADJUNTO A LA FUNCION")

                                    log.write({
                                        'name': 'Correo recibido con adjunto valido'
                                    })
                                    self.env['import.error.line'].create({
                                        'log_id': log.id,
                                        'line_number': '10',
                                        'error_message': "Se pasa el adjunto al modelo excel.from.email",
                                        'data': "Ejecución del modelo fetchmail.server correcta"
                                    })

                                    self.env['excel.from.email'].process_incoming_email(attachment)

                        imap_server.store(email_id, '-FLAGS', '\\Seen')
                        try:
                            res_id = MailThread.with_context(**additionnal_context).message_process(
                                server.object_id.model, msg_data[0][1], save_original=server.original,
                                strip_attachments=(not server.attach))
                        except Exception:
                            _logger.info('Failed to process mail from %s server %s.', server.server_type, server.name,
                                         exc_info=True)
                            failed += 1
                        imap_server.store(email_id, '+FLAGS', '\\Seen')
                        self._cr.commit()
                        count += 1
                    _logger.info("Fetched %d email(s) on %s server %s; %d succeeded, %d failed.", count,
                                 server.server_type, server.name, (count - failed), failed)
                except Exception as e:
                    _logger.info("General failure when trying to fetch mail from %s server %s.", server.server_type,
                                 server.name, exc_info=True)
                    _logger.info("[GENERAL FAILURE REASON]: %s", str(e))
                finally:
                    if imap_server:
                        try:
                            imap_server.close()
                            imap_server.logout()
                        except OSError:
                            _logger.warning('Failed to properly finish imap connection: %s.', server.name,
                                            exc_info=True)
            elif connection_type == 'pop':
                try:
                    while True:
                        failed_in_loop = 0
                        num = 0
                        pop_server = server.connect()
                        (num_messages, total_size) = pop_server.stat()
                        pop_server.list()
                        for num in range(1, min(MAX_POP_MESSAGES, num_messages) + 1):
                            (header, messages, octets) = pop_server.retr(num)
                            message = (b'\n').join(messages)
                            res_id = None
                            try:
                                res_id = MailThread.with_context(**additionnal_context).message_process(
                                    server.object_id.model, message, save_original=server.original,
                                    strip_attachments=(not server.attach))
                                pop_server.dele(num)
                            except Exception:
                                _logger.info('Failed to process mail from %s server %s.', server.server_type,
                                             server.name, exc_info=True)
                                failed += 1
                                failed_in_loop += 1
                            self.env.cr.commit()
                        _logger.info("Fetched %d email(s) on %s server %s; %d succeeded, %d failed.", num,
                                     server.server_type, server.name, (num - failed_in_loop), failed_in_loop)
                        # Stop if (1) no more message left or (2) all messages have failed
                        if num_messages < MAX_POP_MESSAGES or failed_in_loop == num:
                            break
                        pop_server.quit()
                except Exception:
                    _logger.info("General failure when trying to fetch mail from %s server %s.", server.server_type,
                                 server.name, exc_info=True)
                finally:
                    if pop_server:
                        try:
                            pop_server.quit()
                        except OSError:
                            _logger.warning('Failed to properly finish pop connection: %s.', server.name, exc_info=True)
            server.write({'date': fields.Datetime.now()})
        if log.name == 'Registro de ejecución de fetchmail':
            log.unlink()
        return True
