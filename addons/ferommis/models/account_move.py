# -*- coding: utf-8 -*-

from odoo import models, fields, tools, api, _
from datetime import datetime, timedelta
from urllib.parse import quote_plus 
from odoo.addons.base.models.ir_ui_view import keep_query

from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.lib.units import mm

try:
    import base64
except ImportError:
    base64 = None
from io import BytesIO

class AccountMove(models.Model):
    _inherit = ['account.move']

    # def button_draft(self):
    #     if self.move_type in ['out_invoice', 'out_refund']:
    #         super(AccountMove, self).button_draft()
    #     else:
    #         exchange_move_ids = set()
    #         if self:
    #             self.env['account.full.reconcile'].flush_model(['exchange_move_id'])
    #             self.env['account.partial.reconcile'].flush_model(['exchange_move_id'])
    #             self._cr.execute(
    #                 """
    #                     SELECT DISTINCT sub.exchange_move_id
    #                     FROM (
    #                         SELECT exchange_move_id
    #                         FROM account_full_reconcile
    #                         WHERE exchange_move_id IN %s

    #                         UNION ALL

    #                         SELECT exchange_move_id
    #                         FROM account_partial_reconcile
    #                         WHERE exchange_move_id IN %s
    #                     ) AS sub
    #                 """,
    #                 [tuple(self.ids), tuple(self.ids)],
    #             )
    #             exchange_move_ids = set([row[0] for row in self._cr.fetchall()])

    #         for move in self:
    #             if move.id in exchange_move_ids:
    #                 raise UserError(_('You cannot reset to draft an exchange difference journal entry.'))
    #             if move.restrict_mode_hash_table and move.state == 'posted':
    #                 raise UserError(_('You cannot modify a posted entry of this journal because it is in strict mode.'))
    #             # We remove all the analytics entries for this journal
    #             move.mapped('line_ids.analytic_line_ids').unlink()

    #         #   self.mapped('line_ids').remove_move_reconcile()
    #         self.write({'state': 'draft', 'is_move_sent': False})

    def get_invoice_data_toprint(self):

        cfdi_vals = self.sudo()._l10n_mx_edi_decode_cfdi()
        partner_id = self.partner_id
        partner_vat = partner_id.vat
        if partner_id.company_id != self.company_id:
            partner_vat += f" - RFC MÉXICO: {cfdi_vals['customer_rfc']}"
        usage_text = dict(partner_id._fields['l10n_mx_edi_usage'].selection).get(cfdi_vals['usage'])
        regime_text = dict(partner_id._fields['l10n_mx_edi_fiscal_regime'].selection).get(partner_id.l10n_mx_edi_fiscal_regime)
        if cfdi_vals['payment_method'] == 'PUE':
            payment_method_text = 'Pago en una sola exhibición'
        else:
            payment_method_text = 'Pago en parcialidades o diferido'

        export_code = '01'
        export_text = 'No apica' 

        if cfdi_vals['ext_trade_node']:
            export_code = 'xx'
            export_text = 'xxxxxxxxxx'

        full_address = f"{partner_id.street or ''} {partner_id.street2 or ''} {partner_id.city or ''} {partner_id.city_id.name or ''} {partner_id.state_id.name or ''} {partner_id.country_id.name or ''}"
        tax_totals = self.tax_totals
        amt_total = tax_totals['formatted_amount_total'].replace(u'\xa0', u'')
        amt_entero = int(self.amount_total)
        amt_decimal = round(float("0."+amt_total.split(".")[1]),2)
        amt_decimal = (str(amt_decimal).split(".")[1] + "0000")[:2]

        amount_ieps = 0
        amount_iva = 0
        for tax in tax_totals['groups_by_subtotal']['Importe sin impuestos']:
            group_name = tax['tax_group_name']
            group_amount = tax['tax_group_amount']
            if group_name[:4] == 'IEPS':
                amount_ieps += group_amount
            elif group_name[:3] == 'IVA':
                amount_iva += group_amount
        dp = f"{self.currency_id.decimal_places}f"
        expr = '"${:,.' + dp + '}".format(amount_ieps)'
        amt_ieps = eval(expr)
        expr = '"${:,.' + dp + '}".format(amount_iva)'
        amt_iva = eval(expr)

        line_ids, customs_numbers = self._get_invoice_lines() 

        invoice_vals = {
            'number': self.name,
            'stamp_date': cfdi_vals['stamp_date'],
            'emission_date': cfdi_vals['emission_date_str'],
            'date_due': self.invoice_date_due,
            'pm': cfdi_vals['payment_method'],
            'pmt': payment_method_text,
            'pw': self.l10n_mx_edi_payment_method_id.code,
            'pwt': self.l10n_mx_edi_payment_method_id.name,
            'ec': f"{export_code} {export_text}",
            #'ect': export_text,
            'uuid': cfdi_vals['uuid'],
            'certificate': cfdi_vals['certificate_number'],
            'sat_certificate': cfdi_vals['certificate_sat_number'],
            'original_string': cfdi_vals['cadena'],
            'stamp': cfdi_vals['sello'],
            'sat_stamp': cfdi_vals['sello_sat'],
            'use': cfdi_vals['usage'],
            'use_text': usage_text,
            'partner_name': partner_id.name,
            'regime': partner_id.l10n_mx_edi_fiscal_regime,
            'regime_text': regime_text,
            'partner_vat': partner_vat,
            'zip': partner_id.zip,
            'partner_full_address': full_address,
            'customs_numbers': customs_numbers,
            'line_ids': line_ids,
            'amt_untax': tax_totals['formatted_amount_untaxed'].replace(u'\xa0', u''),
            'amt_iva': amt_iva,
            'amt_ieps': amt_ieps,
            'amt_total': tax_totals['formatted_amount_total'].replace(u'\xa0', u''),
            'amt_text': f"{self.currency_id.amount_to_text(amt_entero)} {amt_decimal}/100 {self.currency_id.name}".upper(),
        }
        rfce  = self.l10n_mx_edi_cfdi_supplier_rfc
        rfcr = self.l10n_mx_edi_cfdi_customer_rfc
        total = "%.*f"  % (self.currency_id.decimal_places, self.l10n_mx_edi_cfdi_amount)
        uuid = cfdi_vals['uuid']
        sello = cfdi_vals['sello'][-8:]

        qr_image = self._get_cfdi_qr(rfce, rfcr, total, uuid, sello)
        if qr_image is not None:
            invoice_vals.update({"images": [qr_image]})
    
            return invoice_vals
    
    def _get_cfdi_qr(self, rfce, rfcr, total, uuid, sello):

        options = {'width': 275 * mm, 'height': 275 * mm}
        qr_value = 'https://verificacfdi.facturaelectronica.sat.gob.mx/default.aspx?&id=%s&re=%s&rr=%s&tt=%s&fe=%s' % (
            uuid,
            rfce,
            rfcr,
            total, 
            sello,
        )
        qr_image = qr_value
        ret_val = createBarcodeDrawing('QR', value=qr_value, **options)
        qrcode_image = base64.encodebytes(ret_val.asString('jpg'))

        return qrcode_image
    
    def _get_invoice_lines(self):

        line_ids = []
        customs_number = []
        for line in self.invoice_line_ids:
            line_uom = line.product_uom_id.unspsc_code_id
            tiva = ''
            tieps= ''
            for tax in line.tax_ids:
                if tax.description[:4] == 'IEPS':
                    tieps += f"{tax.description},"
                elif tax.description[:3] == 'IVA':
                    tiva += f"{tax.description},"
            tiva = tiva[:len(tiva)-1]
            tieps = tieps[:len(tieps)-1]
            data = {
                'product_id': line.product_id.unspsc_code_id.code,
                'uom': f"{line_uom.code} {line_uom.name}",
                'product_name': line.name, #line.product_id.get_product_multiline_description_sale(),
                'qty': line.quantity,
                'price': "{:,.4f}".format(line.price_unit),
                'taxobj': '02',
                'tiva': tiva,
                'tieps': tieps,
                'subtotal': "{:,.4f}".format(line.price_subtotal)
            }
            line_ids.append(data)
            if line.l10n_mx_edi_customs_number:
                customs = line.l10n_mx_edi_customs_number.split(",")
                for custom in customs:
                    if custom not in customs_number:
                        customs_number.append(custom)
        
        return line_ids, ",".join(customs_number)