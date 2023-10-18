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

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        res = super(AccountMove, self)._onchange_partner_id()
        for move in self:
            if move.partner_id:
                move.l10n_mx_edi_usage = move.partner_id.l10n_mx_edi_usage
                move.l10n_mx_edi_payment_method_id = move.partner_id.l10n_mx_edi_payment_method_id.id

        return res
    
    def get_invoice_data_toprint(self):

        cfdi_vals = self.sudo()._l10n_mx_edi_decode_cfdi()
        partner_id = self.partner_id
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
            'partner_vat': partner_id.vat,
            'zip': partner_id.zip,
            'partner_full_address': full_address,
            'line_ids': self._get_invoice_lines(),
            'amt_untax': tax_totals['formatted_amount_untaxed'].replace(u'\xa0', u''),
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
        for line in self.invoice_line_ids:
            line_uom = line.product_uom_id.unspsc_code_id
            taxobj =''
            for tax in line.tax_ids:
                taxobj += f"{tax.tax_group_id.id:02},"
            taxobj = taxobj[:len(taxobj)-1]
            data = {
                'product_id': line.product_id.unspsc_code_id.code,
                'uom': f"{line_uom.code} {line_uom.name}",
                'product_name': line.product_id.name,
                'qty': line.quantity,
                'price': "{:,.4f}".format(line.price_unit),
                'taxobj': taxobj,
                'subtotal': "{:,.4f}".format(line.price_subtotal)
            }
            line_ids.append(data)
        
        return line_ids