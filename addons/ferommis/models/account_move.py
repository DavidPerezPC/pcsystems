# -*- coding: utf-8 -*-

from odoo import models, fields, tools, api, _
from datetime import datetime, timedelta
from urllib.parse import quote_plus 
#from odoo.addons.base.models.ir_ui_view import keep_query
from odoo.addons.base.models.ir_qweb import keep_query

from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.lib.units import mm
import html2text

from collections import defaultdict
from lxml import etree
from pytz import timezone
import re
from werkzeug.urls import url_quote_plus

from odoo.addons.l10n_mx_edi.models.l10n_mx_edi_document import (
    CANCELLATION_REASON_SELECTION,
    CANCELLATION_REASON_DESCRIPTION,
    CFDI_CODE_TO_TAX_TYPE,
    CFDI_DATE_FORMAT,
    USAGE_SELECTION,
)
from odoo.exceptions import ValidationError, UserError
from odoo.tools import format_list, frozendict
from odoo.tools.float_utils import float_round
from odoo.tools.sql import column_exists, create_column


try:
    import base64
except ImportError:
    base64 = None
from io import BytesIO

class AccountMove(models.Model):
    _inherit = ['account.move']

    # -------------------------------------------------------------------------
    # CFDI Generation: Payments
    # -------------------------------------------------------------------------

    def _l10n_mx_edi_add_payment_cfdi_values(self, cfdi_values, pay_results):
        """ Prepare the values to render the payment cfdi.

        :param cfdi_values: Prepared cfdi_values.
        :param pay_results: The amounts to consider for each invoice.
                            See '_l10n_mx_edi_cfdi_payment_get_reconciled_invoice_values'.
        :return: The dictionary to render the xml.
        """
        self.ensure_one()
        Document = self.env['l10n_mx_edi.document']

        self._l10n_mx_edi_add_common_cfdi_values(cfdi_values)
        company = cfdi_values['company']
        company_curr = company.currency_id

        # Misc.
        cfdi_values['exportacion'] = '01'
        cfdi_values['forma_de_pago'] = (self.l10n_mx_edi_payment_method_id.code or '').replace('NA', '99')
        cfdi_values['moneda'] = self.currency_id.name
        cfdi_values['num_operacion'] = self.ref

        # Amounts.
        total_in_payment_curr = sum(x['payment_amount_currency'] for x in pay_results['invoice_results'])
        total_in_company_curr = sum(x['balance'] + x['payment_exchange_balance'] for x in pay_results['invoice_results'])
        if self.currency_id == company_curr:
            cfdi_values['monto'] = total_in_company_curr
        else:
            cfdi_values['monto'] = total_in_payment_curr

        # Exchange rate.
        # 'tipo_cambio' is a conditional attribute used to express the exchange rate of the currency on the date the
        # payment was made.
        # The value must reflect the number of Mexican pesos that are equivalent to a unit of the currency indicated
        # in the 'moneda' attribute.
        # It is required when the MonedaP attribute is different from MXN.
        cfdi_values['tipo_cambio_dp'] = 6
        if self.currency_id == company_curr:
            payment_rate = None
        else:
            raw_payment_rate = abs(total_in_company_curr / total_in_payment_curr) if total_in_payment_curr else 0.0
            payment_rate = float_round(raw_payment_rate, precision_digits=cfdi_values['tipo_cambio_dp'])
        cfdi_values['tipo_cambio'] = payment_rate

        # === Create the list of invoice data ===
        invoice_values_list = []
        for invoice_values in pay_results['invoice_results']:
            invoice = invoice_values['invoice']

            inv_cfdi_values = Document._get_company_cfdi_values(invoice.company_id)
            Document._add_certificate_cfdi_values(inv_cfdi_values)
            invoice._l10n_mx_edi_add_invoice_cfdi_values(inv_cfdi_values)

            # Apply the percentage paid to the tax amounts.
            if invoice.amount_total:
                percentage_paid = abs(invoice_values['reconciled_amount'] / invoice.amount_total)
            else:
                percentage_paid = 0.0
            for key in (
                'retenciones_list',
                'traslados_list',
                'local_traslados_list',
                'local_retenciones_list',
            ):
                for tax_values in inv_cfdi_values[key]:
                    for tax_key in ('base', 'importe'):
                        if tax_values[tax_key] is not None:
                            tax_values[tax_key] = invoice.currency_id.round(tax_values[tax_key] * percentage_paid)

            # 'equivalencia' (rate) is a conditional attribute used to express the exchange rate according to the currency
            # registered in the document related. It is required when the currency of the related document is different
            # from the payment currency.
            # The number of units of the currency must be recorded indicated in the related document that are
            # equivalent to a unit of the currency of the payment.
            def calculate_rate(invoice_amount, payment_amount):
                if not payment_amount:
                    return 0.0
                rate = self.currency_id._get_conversion_rate(self.currency_id, invoice.currency_id, self.company_id, self.date)
                converted_invoice_amount = self.currency_id.round(invoice_amount / rate) if rate else 0.0
                converted_payment_amount = invoice.currency_id.round(payment_amount * rate)
                computed_rate =  abs(invoice_amount / payment_amount)
                if (
                    self.currency_id.is_zero(converted_invoice_amount - payment_amount)
                    and invoice.currency_id.is_zero(invoice_amount - converted_payment_amount)
                ):
                    return (rate, computed_rate)
                return (computed_rate, computed_rate)

            if invoice.currency_id == self.currency_id:
                # Same currency.
                rate, computed_rate = (None, None)
            elif invoice.currency_id == company_curr != self.currency_id:
                # Adapt the payment rate to find the reconciled amount of the invoice but expressed in payment currency.
                balance = invoice_values['balance'] + invoice_values['invoice_exchange_balance']
                rate, computed_rate = calculate_rate(balance, invoice_values['payment_amount_currency'])
            elif self.currency_id == company_curr != invoice.currency_id:
                # Adapt the invoice rate to find the reconciled amount of the payment but expressed in invoice currency.
                balance = invoice_values['balance'] + invoice_values['payment_exchange_balance']
                rate, computed_rate = calculate_rate(invoice_values['invoice_amount_currency'], balance)
            else:
                # Both are expressed in different currencies.
                rate, computed_rate = calculate_rate(invoice_values['invoice_amount_currency'], invoice_values['payment_amount_currency'])

            invoice_values_list.append({
                **inv_cfdi_values,
                'id_documento': invoice.l10n_mx_edi_cfdi_uuid,
                'equivalencia': rate,
                'inv_rate': computed_rate,
                'num_parcialidad': invoice_values['number_of_payments'],
                'imp_pagado': invoice_values['reconciled_amount'],
                'imp_saldo_ant': invoice_values['amount_residual_before'],
                'imp_saldo_insoluto': invoice_values['amount_residual_after'],
            })
        cfdi_values['docto_relationado_list'] = invoice_values_list

        # Customer.
        rfcs = set(x['receptor']['rfc'] for x in invoice_values_list)
        if len(rfcs) > 1:
            cfdi_values['errors'] = [_("You can't register a payment for invoices having different RFCs.")]
            return

        customer_values = invoice_values_list[0]['receptor']
        customer = customer_values['customer']
        cfdi_values['receptor'] = customer_values
        cfdi_values['lugar_expedicion'] = cfdi_values['issued_address'].zip

        # Date.
        cfdi_date = datetime.combine(fields.Datetime.from_string(self.date), datetime.strptime('12:00:00', '%H:%M:%S').time())
        cfdi_values['fecha'] = Document._get_datetime_now_with_mx_timezone(cfdi_values, journal=self.journal_id).strftime(CFDI_DATE_FORMAT)
        cfdi_values['fecha_pago'] = cfdi_date.strftime(CFDI_DATE_FORMAT)

        # Bank information.
        payment_method_code = self.l10n_mx_edi_payment_method_id.code
        is_payment_code_emitter_ok = payment_method_code in ('02', '03', '04', '05', '06', '28', '29', '99')
        is_payment_code_receiver_ok = payment_method_code in ('02', '03', '04', '05', '28', '29', '99')
        is_payment_code_bank_ok = payment_method_code in ('02', '03', '04', '28', '29', '99')

        bank_account = customer.bank_ids.filtered(lambda x: x.company_id.id in (False, company.id))[:1]

        partner_bank = bank_account.bank_id
        if partner_bank.country and partner_bank.country.code != 'MX':
            partner_bank_vat = 'XEXX010101000'
        else:  # if no partner_bank (e.g. cash payment), partner_bank_vat is not set.
            partner_bank_vat = partner_bank.l10n_mx_edi_vat

        payment_account_ord = re.sub(r'\s+', '', bank_account.acc_number or '') or None
        payment_account_receiver = re.sub(r'\s+', '', self.journal_id.bank_account_id.acc_number or '') or None

        cfdi_values.update({
            'rfc_emisor_cta_ord': is_payment_code_emitter_ok and partner_bank_vat,
            'nom_banco_ord_ext': is_payment_code_bank_ok and partner_bank.name,
            'cta_ordenante': is_payment_code_emitter_ok and payment_account_ord,
            'rfc_emisor_cta_ben': is_payment_code_receiver_ok and self.journal_id.bank_account_id.bank_id.l10n_mx_edi_vat,
            'cta_beneficiario': is_payment_code_receiver_ok and payment_account_receiver,
        })

        # Taxes.
        cfdi_values.update({
            'monto_total_pagos': total_in_company_curr,
            'mxn_digits': company_curr.decimal_places - 2,
        })

        def update_tax_amount(key, amount):
            if key not in cfdi_values:
                cfdi_values[key] = 0.0
            cfdi_values[key] += amount

        def check_transferred_tax_values(tax_values, tag, tax_class, amount):
            return (
                tax_values['impuesto'] == tag
                and tax_values['tipo_factor'] == tax_class
                and company_curr.compare_amounts(tax_values['tasa_o_cuota'] or 0.0, amount) == 0
            )

        withholding_values_map = defaultdict(lambda: {'importe': 0.0})
        transferred_values_map = defaultdict(lambda: {'base': 0.0, 'importe': 0.0})
        local_retenciones_values_map = defaultdict(lambda: {'base': 0.0, 'importe': 0.0})
        local_traslados_values_map = defaultdict(lambda: {'base': 0.0, 'importe': 0.0})
        pay_rate = cfdi_values['tipo_cambio'] or 1.0
        for cfdi_inv_values in invoice_values_list:
            inv_rate = cfdi_inv_values.pop('inv_rate', False) or 1.0
            to_mxn_rate = pay_rate / inv_rate
            for result_dict, key in (
                (withholding_values_map, 'retenciones_list'),
                (local_retenciones_values_map, 'local_retenciones_list'),
            ):
                for tax_values in cfdi_inv_values[key]:
                    tax_key = frozendict({
                        'impuesto': tax_values['impuesto'],
                        'tipo_factor': tax_values['tipo_factor'],
                        'tasa_o_cuota': tax_values['tasa_o_cuota'],
                        'local_tax_name': tax_values['local_tax_name'],
                    })
                    result_dict[tax_key]['importe'] += tax_values['importe'] / inv_rate

                    tax_amount_mxn = tax_values['importe'] * to_mxn_rate
                    if tax_values['impuesto'] == '001':
                        update_tax_amount('total_retenciones_isr', tax_amount_mxn)
                    elif tax_values['impuesto'] == '002':
                        update_tax_amount('total_retenciones_iva', tax_amount_mxn)
                    elif tax_values['impuesto'] == '003':
                        update_tax_amount('total_retenciones_ieps', tax_amount_mxn)

            for result_dict, key in (
                (transferred_values_map, 'traslados_list'),
                (local_traslados_values_map, 'local_traslados_list'),
            ):
                for tax_values in cfdi_inv_values[key]:
                    tax_key = frozendict({
                        'impuesto': tax_values['impuesto'],
                        'tipo_factor': tax_values['tipo_factor'],
                        'tasa_o_cuota': tax_values['tasa_o_cuota'],
                        'local_tax_name': tax_values['local_tax_name'],
                    })
                    tax_amount = tax_values['importe'] or 0.0
                    result_dict[tax_key]['base'] += tax_values['base'] / inv_rate
                    result_dict[tax_key]['importe'] += tax_amount / inv_rate

                    base_amount_mxn = tax_values['base'] * to_mxn_rate
                    tax_amount_mxn = tax_amount * to_mxn_rate
                    if check_transferred_tax_values(tax_values, '002', 'Tasa', 0.0):
                        update_tax_amount('total_traslados_base_iva0', base_amount_mxn)
                        update_tax_amount('total_traslados_impuesto_iva0', tax_amount_mxn)
                    elif check_transferred_tax_values(tax_values, '002', 'Exento', 0.0):
                        update_tax_amount('total_traslados_base_iva_exento', base_amount_mxn)
                    elif check_transferred_tax_values(tax_values, '002', 'Tasa', 0.08):
                        update_tax_amount('total_traslados_base_iva8', base_amount_mxn)
                        update_tax_amount('total_traslados_impuesto_iva8', tax_amount_mxn)
                    elif check_transferred_tax_values(tax_values, '002', 'Tasa', 0.16):
                        update_tax_amount('total_traslados_base_iva16', base_amount_mxn)
                        update_tax_amount('total_traslados_impuesto_iva16', tax_amount_mxn)

        # Rounding global tax amounts.
        for dictionary in (
            withholding_values_map,
            transferred_values_map,
            local_retenciones_values_map,
            local_traslados_values_map,
        ):
            for values in dictionary.values():
                if 'base' in values:
                    values['base'] = self.currency_id.round(values['base'])
                values['importe'] = self.currency_id.round(values['importe']) 

        for key in (
            'total_traslados_base_iva0',
            'total_traslados_impuesto_iva0',
            'total_traslados_base_iva_exento',
            'total_traslados_base_iva8',
            'total_traslados_impuesto_iva8',
            'total_traslados_base_iva16',
            'total_traslados_impuesto_iva16',
            'total_retenciones_isr',
            'total_retenciones_iva',
            'total_retenciones_ieps',
        ):
            if key in cfdi_values:
                cfdi_values[key] = company_curr.round(cfdi_values[key])
            else:
                cfdi_values[key] = None

        for target_key, source_dict in (
            ('retenciones_list', withholding_values_map),
            ('traslados_list', transferred_values_map),
            ('local_retenciones_list', local_retenciones_values_map),
            ('local_traslados_list', local_traslados_values_map),
        ):
            cfdi_values[target_key] = [
                {**k, **v}
                for k, v in source_dict.items()
            ]

        # Cleanup attributes for Exento taxes.
        for key in (
            'traslados_list',
            'local_traslados_list',
        ):
            for tax_values in cfdi_values[key]:
                if tax_values['tipo_factor'] == 'Exento':
                    tax_values['importe'] = None

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

    def _format_currency(self, amount):
        dp = f"{self.currency_id.decimal_places}f"
        expr = '"${:,.' + dp + '}".format('+str(amount)+')'
        return eval(expr).replace("$-","-$")
    
    def get_invoice_data_toprint(self):
        cfdi_vals = self._l10n_mx_edi_get_extra_invoice_report_values()
        partner_id = self.partner_id
        partner_vat = partner_id.vat
        if partner_id.country_id != self.company_id.country_id:
            partner_vat += f" - RFC MÉXICO: {cfdi_vals['customer_rfc']}"
        usage_text = f"- {cfdi_vals['usage_desc']}"
        regime_text = dict(partner_id._fields['l10n_mx_edi_fiscal_regime'].selection).get(partner_id.l10n_mx_edi_fiscal_regime)
        if cfdi_vals['payment_method'] == 'PUE':
            payment_method_text = 'Pago en una sola exhibición'
        else:
            payment_method_text = 'Pago en parcialidades o diferido'

        export_code = '01'
        export_text = 'No aplica'
        msg_usd = "" 
        if self.currency_id != self.company_id.currency_id:
            msg_usd = "EL PAGO DEBERÁ SER EN DÓLARES ESTADOUNIDENSES O SU EQUIVALENTE EN PESOS AL DÍA"

        notas = ""
        if self.narration:
            h = html2text.HTML2Text()
            notas = h.handle(self.narration).strip()

        uuid_related = ''
        if self.l10n_mx_edi_cfdi_origin:
            uuid_related = self.l10n_mx_edi_cfdi_origin[3:]

        if self.l10n_mx_edi_external_trade: 
            export_code = 'xx'
            export_text = 'xxxxxxxxxx'

        full_address = f"{partner_id.street or ''} {partner_id.street2 or ''} {partner_id.city or ''} {partner_id.city_id.name or ''} {partner_id.state_id.name or ''} {partner_id.country_id.name or ''}"
        tax_totals = self.tax_totals
        amt_total = f"{self.amount_total}"
        amt_entero = int(self.amount_total)
        amt_decimal = round(float("0."+amt_total.split(".")[1]),2)
        amt_decimal = (str(amt_decimal).split(".")[1] + "0000")[:2]

        amount_ieps = 0
        amount_iva = 0
        for tax in tax_totals['subtotals'][0]['tax_groups']:
            group_name = tax['group_name']
            group_amount = tax['tax_amount_currency']
            if group_name[:4] == 'IEPS':
                amount_ieps += group_amount
            elif group_name[:3] == 'IVA':
                amount_iva += group_amount

        amt_ieps = self._format_currency(amount_ieps)
        amt_iva = self._format_currency(amount_iva)

        line_ids, customs_numbers, predial_account = self.get_invoice_ferommis_lines() 

        if predial_account:
            predial_account = f"CUENTA PREDIAL: {predial_account}"

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
            'cuenta_predial': predial_account,
            #'ect': export_text,
            'uuid': cfdi_vals['uuid'],
            'uui_related': uuid_related,
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
            'amt_untax': self._format_currency(self.amount_untaxed),
            'amt_iva': amt_iva,
            'amt_ieps': amt_ieps,
            'amt_total': self._format_currency(self.amount_total),
            'amt_text': self.amount_total_words,
            'msg_usd': msg_usd,
            'notas': notas,
        }
        rfce  = cfdi_vals['supplier_rfc']
        rfcr = cfdi_vals['customer_rfc']
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
    
    def get_invoice_ferommis_lines(self):

        line_ids = []
        customs_number = []
        predial_account = []
        for line in self.invoice_line_ids:
            line_uom = line.product_uom_id.unspsc_code_id
            tiva = ''
            tieps= ''
            for tax in line.tax_ids:
                if tax.name[:4] == 'IEPS':
                    tieps += f"{tax.name},"
                elif tax.name[:3] == 'IVA':
                    tiva += f"{tax.name},"            
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
            slc = self.env['stock.landed.cost']
            if line.l10n_mx_edi_customs_number:
                customs = line.l10n_mx_edi_customs_number.split(",")
                for custom in customs:
                    domain = [('l10n_mx_edi_customs_number', '=', custom)]
                    slcobj = slc.search(domain)
                    if custom not in customs_number:
                        ccustom = custom
                        if slcobj and slcobj[0].customs_name:
                            slcobj = slcobj[0]
                            customname = dict(slcobj._fields['customs_name'].selection).get(slcobj.customs_name)
                            ccustom += f" ADUANA {customname.upper()} {datetime.strftime(slcobj.customs_date, '%d/%m/%Y')} "
                        customs_number.append(ccustom)

            if line.product_id.l10n_mx_edi_predial_account:
                predial_account.append(line.product_id.l10n_mx_edi_predial_account)
        
        return line_ids, ",".join(customs_number), ",".join(predial_account)


    def get_journal_data_toprint(self):
   
        move_id = self.id
        journal_id = self.journal_id.id
        name = self.name
    
        move_ids = [move_id]
        for line in self.line_ids:

            for debit in line.matched_debit_ids:
                if debit.credit_move_id and debit.credit_move_id.move_id.id != move_id:
                    move_ids.append(debit.credit_move_id.move_id.id)
                if debit.exchange_move_id:
                    move_ids.append(debit.exchange_move_id.id)
                if debit.debit_move_id and debit.debit_move_id.move_id.id != move_id:
                    move_ids.append(debit.debit_move_id.move_id.id)
            for credit in line.matched_credit_ids:
                if credit.debit_move_id and credit.debit_move_id.move_id.id != move_id:
                    move_ids.append(credit.debit_move_id.move_id.id)
                if credit.exchange_move_id:
                    move_ids.append(credit.exchange_move_id.id)
                if credit.credit_move_id and credit.credit_move_id.move_id.id != move_id:
                    move_ids.append(credit.credit_move_id.move_id.id)

        cash_basis_move_ids = self.env['account.move'].search([
            ('tax_cash_basis_origin_move_id', 'in', move_ids),
            ('state', '=', 'posted'),
        ])
        move_ids += cash_basis_move_ids.ids
        move_ids = str(tuple(move_ids))

 	                # case when sum(aml.debit) > 0 then to_char(sum(aml.debit), '999,999,999.9999') else '' end debe, 
 	                # case when sum(aml.credit) > 0 then to_char(sum(aml.credit), '999,999,999.9999') else '' end haber
        sql = f"""
                select aml.move_id, aml.move_name, to_char( aml.date, 'DD/MM/YYYY') date,
                    concat('[', aa.code_store->>'1', '] ', aa."name"->>'en_US') AccCodeName,
                    sum(aml.debit) as debe,
                    sum(aml.credit) as haber
                from account_move am
                    join account_move_line aml on (aml.move_id = am.id)
                    join account_account aa on (aa.id = aml.account_id )
                where am.id in {move_ids} and aml.account_id != 38
                group by 1, 2, 3, 4;
            """

        self._cr.execute(sql)
        result = self._cr.dictfetchall()

        data ={
            'name': name,
            'journal_name': self.journal_id.name,
            'date': self.date,
            'partner_name': self.partner_id.name,
            'line_ids': result,
            'total_debe': sum(d.get('debe', 0) for d in result),
            'total_haber': sum(d.get('haber', 0) for d in result)
        } 

        return data 


            
            