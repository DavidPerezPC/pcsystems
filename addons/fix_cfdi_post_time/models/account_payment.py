# -*- coding: utf-8 -*-
from collections import defaultdict
from odoo.tools.float_utils import float_round, float_is_zero
from odoo import models, fields, api
from datetime import datetime, timedelta

import re

EQUIVALENCIADR_PRECISION_DIGITS = 10
class AccountPayment(models.Model):
    _inherit = ['account.payment']

    l10n_mx_edi_has_errors = fields.Boolean(
        string="Errores en edi",
        compute="_compute_edi_status",
        store=False
    )
    #amount = fields.Monetary(digits=(12,2))

    #api.depends("l10n_mx_sat_status")
    def _compute_edi_status(self):

        for payment in self:
            payment.l10n_mx_edi_has_errors = False
            for edi in payment.move_id.edi_document_ids:
                 payment.l10n_mx_edi_has_errors = (edi.state == 'to_send' and edi.blocking_level == 'error')
   
    def fix_post_time(self):

        for payment in self:
            move = payment.move_id
            move.l10n_mx_edi_post_time = move.l10n_mx_edi_post_time - timedelta(hours=1)

# class AccountEdiFormat(models.Model):
#     _inherit = 'account.edi.format'

#     # -------------------------------------------------------------------------
#     # CFDI Generation: Payments
#     # -------------------------------------------------------------------------

#     def _l10n_mx_edi_get_payment_cfdi_values(self, move):

#         def get_tax_cfdi_name(env, tax_detail_vals):
#             tags = set()
#             for detail in tax_detail_vals['group_tax_details']:
#                 for tag in env['account.tax.repartition.line'].browse(detail['tax_repartition_line_id']).tag_ids:
#                     tags.add(tag)
#             tags = list(tags)
#             if len(tags) == 1:
#                 return {'ISR': '001', 'IVA': '002', 'IEPS': '003'}.get(tags[0].name)
#             elif tax_detail_vals['tax'].l10n_mx_tax_type == 'Exento':
#                 return '002'
#             else:
#                 return None

#         def divide_tax_details(env, invoice, tax_details, amount_paid):
#             percentage_paid = amount_paid / invoice.amount_total
#             precision = 2
#             for detail in tax_details['tax_details'].values():
#                 tax = detail['tax']
#                 tax_amount = abs(tax.amount) / 100.0 if tax.amount_type != 'fixed' else abs(detail['tax_amount_currency'] / detail['base_amount_currency'])
#                 base_val_proportion = float_round(detail['base_amount_currency'] * percentage_paid, precision)
#                 tax_val_proportion = float_round(base_val_proportion * tax_amount, precision)
#                 detail.update({
#                     'base_val_prop_amt_curr': base_val_proportion,
#                     'tax_val_prop_amt_curr': tax_val_proportion if tax.l10n_mx_tax_type != 'Exento' else False,
#                     'tax_class': get_tax_cfdi_name(env, detail),
#                     'tax_amount': tax_amount,
#                 })
#             return tax_details

#         if move.payment_id:
#             _liquidity_line, counterpart_lines, _writeoff_lines = move.payment_id._seek_for_lines()
#             currency = counterpart_lines.currency_id
#             total_amount_currency = abs(sum(counterpart_lines.mapped('amount_currency')))
#             total_amount = abs(sum(counterpart_lines.mapped('balance')))
#         else:
#             counterpart_vals = move.statement_line_id._prepare_move_line_default_vals()[1]
#             currency = self.env['res.currency'].browse(counterpart_vals['currency_id'])
#             total_amount_currency = abs(counterpart_vals['amount_currency'])
#             total_amount = abs(counterpart_vals['debit'] - counterpart_vals['credit'])

#         # === Decode the reconciliation to extract invoice data ===
#         pay_rec_lines = move.line_ids.filtered(lambda line: line.account_type in ('asset_receivable', 'liability_payable'))
#         exchange_move_x_invoice = {}
#         reconciliation_vals = defaultdict(lambda: {
#             'amount_currency': 0.0,
#             'balance': 0.0,
#             'exchange_balance': 0.0,
#         })
#         for match_field in ('credit', 'debit'):

#             # Peek the partials linked to exchange difference first in order to separate them from the partials
#             # linked to invoices.
#             for partial in pay_rec_lines[f'matched_{match_field}_ids'].sorted(lambda x: not x.exchange_move_id):
#                 counterpart_move = partial[f'{match_field}_move_id'].move_id
#                 if counterpart_move.l10n_mx_edi_cfdi_request:
#                     # Invoice.

#                     # Gather all exchange moves.
#                     if partial.exchange_move_id:
#                         exchange_move_x_invoice[partial.exchange_move_id] = counterpart_move

#                     invoice_vals = reconciliation_vals[counterpart_move]
#                     invoice_vals['amount_currency'] += partial[f'{match_field}_amount_currency']
#                     invoice_vals['balance'] += partial.amount
#                 elif counterpart_move in exchange_move_x_invoice:
#                     # Exchange difference.
#                     invoice_vals = reconciliation_vals[exchange_move_x_invoice[counterpart_move]]
#                     invoice_vals['exchange_balance'] += partial.amount

#         # === Create remaining values to create the CFDI ===
#         if currency == move.company_currency_id:
#             # Same currency
#             payment_exchange_rate = None
#         else:
#             # Multi-currency
#             payment_exchange_rate = float_round(
#                 total_amount / total_amount_currency,
#                 precision_digits=6,
#                 rounding_method='UP',
#             )

#         # === Create the list of invoice data ===
#         invoice_vals_list = []
#         for invoice, invoice_vals in reconciliation_vals.items():

#             # Compute 'number_of_payments' & add amounts from exchange difference.
#             payment_ids = set()
#             inv_pay_rec_lines = invoice.line_ids.filtered(lambda line: line.account_type in ('asset_receivable', 'liability_payable'))
#             for field in ('debit', 'credit'):
#                 for partial in inv_pay_rec_lines[f'matched_{field}_ids']:
#                     counterpart_move = partial[f'{field}_move_id'].move_id

#                     if counterpart_move.payment_id or counterpart_move.statement_line_id:
#                         payment_ids.add(counterpart_move.id)
#             number_of_payments = len(payment_ids)

#             if invoice.currency_id == currency:
#                 # Same currency
#                 invoice_exchange_rate = None
#             elif currency == move.company_currency_id:
#                 # Payment expressed in MXN but the invoice is expressed in another currency.
#                 # The payment has been reconciled using the currency of the invoice, not the MXN.
#                 # Then, we retrieve the rate from amounts gathered from the reconciliation using the balance of the
#                 # exchange difference line allowing to switch from the "invoice rate" to the "payment rate".
#                 invoice_exchange_rate = float_round(
#                     invoice_vals['amount_currency'] / (invoice_vals['balance'] + invoice_vals['exchange_balance']),
#                     precision_digits=EQUIVALENCIADR_PRECISION_DIGITS,
#                     rounding_method='UP',
#                 )
#             elif invoice.currency_id == move.company_currency_id:
#                 # Invoice expressed in MXN but Payment expressed in other currency
#                 invoice_exchange_rate = payment_exchange_rate
#             else:
#                 # Multi-currency
#                 invoice_exchange_rate = float_round(
#                     invoice_vals['amount_currency'] / invoice_vals['balance'],
#                     precision_digits=6,
#                     rounding_method='UP',
#                 )

#             # for CFDI 4.0
#             cfdi_values = self._l10n_mx_edi_get_invoice_cfdi_values(invoice)
#             tax_details_transferred = divide_tax_details(self.env, invoice, cfdi_values['tax_details_transferred'],
#                                                          invoice_vals['amount_currency'])
#             tax_details_withholding = divide_tax_details(self.env, invoice, cfdi_values['tax_details_withholding'],
#                                                          invoice_vals['amount_currency'])

#             invoice_vals_list.append({
#                 'invoice': invoice,
#                 'exchange_rate': invoice_exchange_rate,
#                 'payment_policy': invoice.l10n_mx_edi_payment_policy,
#                 'number_of_payments': number_of_payments,
#                 'amount_paid': invoice_vals['amount_currency'],
#                 'amount_before_paid': invoice.amount_residual + invoice_vals['amount_currency'],
#                 'tax_details_transferred': tax_details_transferred,
#                 'tax_details_withholding': tax_details_withholding,
#                 'equivalenciadr_precision_digits': EQUIVALENCIADR_PRECISION_DIGITS,
#                 **self._l10n_mx_edi_get_serie_and_folio(invoice),
#             })

#         payment_method_code = move.l10n_mx_edi_payment_method_id.code
#         is_payment_code_emitter_ok = payment_method_code in ('02', '03', '04', '05', '06', '28', '29', '99')
#         is_payment_code_receiver_ok = payment_method_code in ('02', '03', '04', '05', '28', '29', '99')
#         is_payment_code_bank_ok = payment_method_code in ('02', '03', '04', '28', '29', '99')

#         bank_accounts = move.partner_id.commercial_partner_id.bank_ids.filtered(lambda x: x.company_id.id in (False, move.company_id.id))

#         partner_bank = bank_accounts[:1].bank_id
#         if partner_bank.country and partner_bank.country.code != 'MX':
#             partner_bank_vat = 'XEXX010101000'
#         else:  # if no partner_bank (e.g. cash payment), partner_bank_vat is not set.
#             partner_bank_vat = partner_bank.l10n_mx_edi_vat

#         payment_account_ord = re.sub(r'\s+', '', bank_accounts[:1].acc_number or '') or None
#         payment_account_receiver = re.sub(r'\s+', '', move.journal_id.bank_account_id.acc_number or '') or None

#         # CFDI 4.0: prepare the tax summaries
#         rate_payment_curr_mxn_40 = payment_exchange_rate or 1
#         mxn_currency = self.env["res.currency"].search([('name', '=', 'MXN')], limit=1)
#         total_taxes_paid = {}
#         total_taxes_withheld = {
#             '001': {'amount_curr': 0.0, 'amount_mxn': 0.0},
#             '002': {'amount_curr': 0.0, 'amount_mxn': 0.0},
#             '003': {'amount_curr': 0.0, 'amount_mxn': 0.0},
#             None: {'amount_curr': 0.0, 'amount_mxn': 0.0},
#         }
#         for inv_vals in invoice_vals_list:
#             wht_detail = list(inv_vals['tax_details_withholding']['tax_details'].values())
#             trf_detail = list(inv_vals['tax_details_transferred']['tax_details'].values())
#             for detail in wht_detail + trf_detail:
#                 tax = detail['tax']
#                 tax_class = detail['tax_class']
#                 key = (float_round(tax.amount / 100, 6), tax.l10n_mx_tax_type, tax_class)
#                 base_val_pay_curr = detail['base_val_prop_amt_curr'] / (inv_vals['exchange_rate'] or 1.0)
#                 tax_val_pay_curr = detail['tax_val_prop_amt_curr'] / (inv_vals['exchange_rate'] or 1.0)
#                 if key in total_taxes_paid:
#                     total_taxes_paid[key]['base_value'] += base_val_pay_curr
#                     total_taxes_paid[key]['tax_value'] += tax_val_pay_curr
#                 elif tax.amount >= 0:
#                     total_taxes_paid[key] = {
#                         'base_value': base_val_pay_curr,
#                         'tax_value': tax_val_pay_curr,
#                         'tax_amount': float_round(detail['tax_amount'], 6),
#                         'tax_type': tax.l10n_mx_tax_type,
#                         'tax_class': tax_class,
#                         'tax_spec': 'W' if tax.amount < 0 else 'T',
#                     }
#                 else:
#                     total_taxes_withheld[tax_class]['amount_curr'] += tax_val_pay_curr

#         # CFDI 4.0: rounding needs to be done after all DRs are added
#         for v in total_taxes_paid.values():
#             v['base_value'] = float_round(v['base_value'], move.currency_id.decimal_places)
#             v['tax_value'] = float_round(v['tax_value'], move.currency_id.decimal_places)
#             v['base_value_mxn'] = float_round(v['base_value'] * rate_payment_curr_mxn_40, 2)
#             v['tax_value_mxn'] = float_round(v['tax_value'] * rate_payment_curr_mxn_40, 2)
#         for v in total_taxes_withheld.values():
#             v['amount_curr'] = float_round(v['amount_curr'], move.currency_id.decimal_places)
#             v['amount_mxn'] = float_round(v['amount_curr'] * rate_payment_curr_mxn_40, 2)

#         cfdi_values = {
#             **self._l10n_mx_edi_get_common_cfdi_values(move),
#             'invoice_vals_list': invoice_vals_list,
#             'currency': currency,
#             'amount': total_amount_currency,
#             'amount_mxn': float_round(total_amount_currency * rate_payment_curr_mxn_40, 2),
#             'rate_payment_curr_mxn': payment_exchange_rate,
#             'rate_payment_curr_mxn_40': rate_payment_curr_mxn_40,
#             'emitter_vat_ord': is_payment_code_emitter_ok and partner_bank_vat,
#             'bank_vat_ord': is_payment_code_bank_ok and partner_bank.name,
#             'payment_account_ord': is_payment_code_emitter_ok and payment_account_ord,
#             'receiver_vat_ord': is_payment_code_receiver_ok and move.journal_id.bank_account_id.bank_id.l10n_mx_edi_vat,
#             'payment_account_receiver': is_payment_code_receiver_ok and payment_account_receiver,
#             'cfdi_date': move.l10n_mx_edi_post_time.strftime('%Y-%m-%dT%H:%M:%S'),
#             'tax_summary': total_taxes_paid,
#             'withholding_summary': total_taxes_withheld,
#         }
#         cfdi_payment_datetime = datetime.combine(fields.Datetime.from_string(move.date), datetime.strptime('12:00:00', '%H:%M:%S').time())
#         cfdi_values['cfdi_payment_date'] = cfdi_payment_datetime.strftime('%Y-%m-%dT%H:%M:%S')

#         if cfdi_values['customer'].country_id.l10n_mx_edi_code != 'MEX':
#             cfdi_values['customer_fiscal_residence'] = cfdi_values['customer'].country_id.l10n_mx_edi_code
#         else:
#             cfdi_values['customer_fiscal_residence'] = None
#         return cfdi_values



  