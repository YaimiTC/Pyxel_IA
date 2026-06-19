# Demo del expediente (lead 17, Mipyme) con casos del flujo de 3 pasos
# y los veredictos de la IA (Apto / Dudoso / Rechazado).
import base64
from odoo import fields

lead = env['crm.lead'].browse(17)
Doc = env['pyxel.lead.document']

lead.accreditation_document_ids.unlink()
Doc.build_expediente(lead, 'Mipyme', {})
docs = lead.accreditation_document_ids.sorted('sequence')

pdf_demo = base64.b64encode(b'%PDF-1.4 demo expediente acreditacion')


def mkatt(label):
    return env['ir.attachment'].create({
        'name': label,
        'datas': pdf_demo,
        'res_model': 'res.partner',
        'res_id': lead.partner_id.id,
        'type': 'binary',
        'mimetype': 'application/pdf',
    }).id


now = fields.Datetime.now()

# d[0] -> APROBADO TOTAL (IA Apto + datos OCR, abogada y comercial aprobaron)
docs[0].write({'attachment_id': mkatt(docs[0].document_label), 'upload_date': now,
               'ai_state': 'passed', 'ai_confidence': 96, 'ai_quality': 92,
               'ai_extracted_data': 'NIT: 12345678901\nNombre: Probando S.A.\nVence: 2028-05-30',
               'lawyer_state': 'approved', 'commercial_state': 'approved'})
# d[1] -> RECHAZADO POR LA IA (no es el documento correcto)
docs[1].write({'attachment_id': mkatt(docs[1].document_label), 'upload_date': now,
               'ai_state': 'rejected', 'ai_confidence': 21, 'ai_quality': 38,
               'ai_reason': 'El documento subido no parece un registro mercantil. '
                            'Se detectó un comprobante de pago. Suba el documento correcto.'})
# d[2] -> DUDOSO POR LA IA (calidad baja)
docs[2].write({'attachment_id': mkatt(docs[2].document_label), 'upload_date': now,
               'ai_state': 'doubt', 'ai_confidence': 57, 'ai_quality': 44,
               'ai_reason': 'Imagen poco legible: bordes cortados y bajo contraste. '
                            'No se pudo leer el número del NIT con seguridad.'})
# d[3] -> RECHAZADO POR LA ABOGADA (IA Apto, motivo visible al cliente)
docs[3].write({'attachment_id': mkatt(docs[3].document_label), 'upload_date': now,
               'ai_state': 'passed', 'ai_confidence': 81, 'ai_quality': 85,
               'lawyer_notes': 'Nota interna: contrato sin sello en pág. 2.',
               'lawyer_reason': 'El contrato bancario está vencido. Suba la versión vigente.',
               'lawyer_state': 'rejected', 'commercial_state': 'blocked'})
# d[4] -> EN REVISIÓN COMERCIAL (IA Apto, abogada aprobó, comercial pendiente)
docs[4].write({'attachment_id': mkatt(docs[4].document_label), 'upload_date': now,
               'ai_state': 'passed', 'ai_confidence': 89, 'ai_quality': 90,
               'lawyer_state': 'approved', 'lawyer_notes': 'Documentación legal correcta.',
               'commercial_state': 'to_review'})

env.cr.commit()
out = ['%s[ia=%s]->%s' % (d.document_label[:18], d.ai_state, d.portal_state) for d in docs]
print('DEMO_IA_OK ' + ' | '.join(out))
