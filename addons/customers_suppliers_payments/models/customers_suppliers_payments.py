# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

# MAPPED_TAXES = {
#      1: 'iva_0_',
#      2: 'iva_16_',
#      3: 'ret_iva_4_',
#      5: 'ret_isr_arr_',
#     10: 'iva_16_',
#     19: 'iva_exento_',
#     24: 'iva_8_',
#     25: 'ret_isr_hon_',
#     26: 'ret_iva_hon_',
#     36: 'ret_iva_hon_',
#     28: 'ret_isr_125_',
#     29: 'ret_iva_arr_',
#     34: 'ret_iva_arr_',
#     35: 'ret_iva_arr_',
#     30: 'iva_0_',
#     31: 'ret_iva_4_',
#     33: 'iva_exento_',
#     37: 'iva_16_',
#     38: 'ieps_6_',
# }
MAPPED_TAXES = {
     3: "ret_iva_4_",
     4: "ret_iva_arr_",
     5: "ret_isr_arr_",
     6: "ret_isr_hon_",
     7: "ret_iva_arr_",
     8: "ret_iva_hon_",
     5: "ret_isr_arr_",
     9: "iva_0_",
    10: "iva_16_",
    11: "iva_8_",
    13: "ieps_6_",
    17: "ret_iva_hon_",
    18: "ret_isr_125_",
    19: "iva_exento_",
    20: "ret_iva_hon_",
    21: "ret_iva_arr_",
    22: "iva_0_",
    23: "ret_iva_hon_",
    24: "ret_isr_hon_",
    26: "ret_iva_hon_",
    27: "ret_iva_hon_",
    38: "ret_isr_125_",
    40: "iva_exento_",
    52: "ret_iva_arr_",
    53: "ret_iva_4_",
    56: "ret_iva_arr_",
    57: "ret_iva_hon_",
    #62: "no_objeto_",
    73: "iva_16_",
}

class CustomerSuppliersPayments(models.Model):
    _name = 'customers.suppliers.payments'
    _description = 'Customer/Supplier Payments'

    move_id = fields.Many2one('account.move', string='Invoice', required=True)
    invoice_date = fields.Date(string='Invoice Date', readonly=True)
    invoice = fields.Char(string='Invoice Number', readonly=True)
    invoice_ref = fields.Many2one('account.account', string='Invoice Concept', readonly=True)
    invoice_taxes = fields.Text(string='Invoices Taxes', readonly=True)
    invoice_uuid = fields.Char(string='Invoice UUID', related='move_id.l10n_mx_edi_cfdi_uuid', readonly=True, store=True)
    invoice_amount = fields.Monetary(string='Invoice Amount', compute="_compute_invoice_amount", readonly=True)
    invoice_amount_currency = fields.Monetary(string='Invoice Amount Currency', compute="_compute_invoice_amount", readonly=True)
    cfdi_payment_method = fields.Selection(
        [('PPD', 'PPD'), ('PUE', 'PUE')],
        related="move_id.l10n_mx_edi_payment_policy",
        string='CFDI Payment Method',
        readonly=True,
        store=True
    )
    move_type = fields.Selection(
        [('entry', 'Journal Entry'), ('out_invoice', 'Customer Invoice'),
         ('in_invoice', 'Vendor Bill'), ('out_refund', 'Customer Refund'),
         ('in_refund', 'Vendor Credit Note')],
        string='Move Type', related='move_id.move_type', readonly=True, store=True
    )
    payment_id = fields.Many2one('account.move', string='Payment', required=True)
    payment_uuid = fields.Char(string='Payment UUID', related='payment_id.l10n_mx_edi_cfdi_uuid', readonly=True, store=True)
    payment_date = fields.Date(string='Payment Date', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Contact', readonly=True)
    partner_vat = fields.Char(string='Partner VAT', related='partner_id.vat', readonly=True, store=True)
    amount = fields.Monetary(string='Payment Amount MXN', readonly=True)
    amount_currency = fields.Monetary(string='Payment Amount Currency', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', related='payment_id.currency_id', readonly=True)
    currency_rate = fields.Float(string='Currency Rate', digits=(12, 6), readonly=True)
    payment_move = fields.Char(string='Payment Move', readonly=True)
    payment_journal_id = fields.Many2one('account.journal', string='Payment Journal', readonly=True)
    payment_account_id = fields.Many2one(
        'account.account', string='Payment Account',
        related='payment_journal_id.default_account_id', readonly=True, store=True)
    reconcile_type = fields.Selection(
        [('full', 'Full Reconciliation'), ('partial', 'Partial Reconciliation')],
        string='Reconciliation Type', readonly=True
    )
    payment_type = fields.Selection(
        [('payment', 'Payment'), ('credit_note', 'Credit Note')],
        string='Payment Type', readonly=True
    )

    # Impuestos
    iva_16_base = fields.Float(string='IVA 16% Base', readonly=True)
    iva_16_tax = fields.Float(string='IVA 16% Tax', readonly=True)
    iva_exento_base = fields.Float(string='IVA Exento Base', readonly=True)
    iva_exento_tax = fields.Float(string='IVA Exento Tax', readonly=True)
    iva_0_base = fields.Float(string='IVA 0% Base', readonly=True)
    iva_0_tax = fields.Float(string='IVA 0% Tax', readonly=True)
    iva_8_base = fields.Float(string='IVA 8% Base', readonly=True)
    iva_8_tax = fields.Float(string='IVA 8% Tax', readonly=True)
    ret_iva_4_base = fields.Float(string='Ret IVA 4% Base', readonly=True)
    ret_iva_4_tax = fields.Float(string='Ret IVA 4% Tax', readonly=True)
    ret_iva_hon_base = fields.Float(string='Ret IVA Hon. Base', readonly=True)
    ret_iva_hon_tax = fields.Float(string='Ret IVA Hon. Tax', readonly=True)
    ret_iva_arr_base = fields.Float(string='Ret IVA Arr. Base', readonly=True)
    ret_iva_arr_tax = fields.Float(string='Ret IVA Arr. Tax', readonly=True)
    ret_isr_hon_base = fields.Float(string='Ret ISR Hon. Base', readonly=True)
    ret_isr_hon_tax = fields.Float(string='Ret ISR Hon. Tax', readonly=True)
    ret_isr_arr_base = fields.Float(string='Ret ISR Arr. Base', readonly=True)
    ret_isr_arr_tax = fields.Float(string='Ret ISR Arr. Tax', readonly=True)
    ret_isr_125_base = fields.Float(string='Ret ISR 1.25% Base', readonly=True)
    ret_isr_125_tax = fields.Float(string='Ret ISR 1.25% Tax', readonly=True)
    ieps_6_base = fields.Float(string='Ret IEPS 6% Base', readonly=True)
    ieps_6_tax = fields.Float(string='Ret IEPS 6% Tax', readonly=True)
    no_objeto_base = fields.Float(string='No Objeto Base', readonly=True)
    no_objeto_tax = fields.Float(string='No Objeto Tax', readonly=True)

    @api.depends('move_id.amount_total_signed', 'move_id.amount_total_in_currency_signed')
    def _compute_invoice_amount(self):
        for record in self:
            if record.move_id.company_id.currency_id.id != record.move_id.currency_id.id:
                record.invoice_amount_currency = abs(record.move_id.amount_total_in_currency_signed)
                record.invoice_amount = abs(record.move_id.amount_total_signed)
            else:
                record.invoice_amount_currency = 0
                record.invoice_amount = abs(record.move_id.amount_total_signed)

    def get_all_reconciled_payments(self, start_date, end_date):
        if not start_date or not end_date:
            raise ValueError("Debes proporcionar fecha inicial y final.")
        if start_date > end_date:
            raise ValueError("La fecha inicial no puede ser mayor que la final.")

        # Eliminar registros del periodo antes de recrearlos
        self.env['customers.suppliers.payments'].search([
            ('payment_date', '>=', start_date),
            ('payment_date', '<=', end_date),
        ]).unlink()

        # Facturas con pagos/abonos en el rango via partial reconciles
        moves = self._find_invoices_with_payments(start_date, end_date)
        created = 0

        for move in moves:
            breakdown = move._get_paid_tax_breakdown(start_date, end_date)
            for event in breakdown:
                vals = self._build_record_vals(move, event)
                if vals:
                    self.create(vals)
                    created += 1

        _logger.info("customers.suppliers.payments: %d registros creados para %s - %s",
                     created, start_date, end_date)

    def _find_invoices_with_payments(self, date_from, date_to):
        """Facturas/NC con conciliaciones parciales en el rango de fechas."""
        partials = self.env['account.partial.reconcile'].search([
            ('max_date', '>=', date_from),
            ('max_date', '<=', date_to),
        ])
        if not partials:
            return self.env['account.move']

        lines = partials.debit_move_id | partials.credit_move_id
        move_ids = lines.move_id.ids

        return self.env['account.move'].search([
            ('id', 'in', move_ids),
            ('state', '=', 'posted'),
            ('move_type', 'in', (
                'out_invoice', 'out_refund', 'in_invoice', 'in_refund')),
        ], order='invoice_date, name')

    def _build_record_vals(self, move, event):
        """Construye el dict de valores para crear un registro."""
        counterpart = event['counterpart_move']
        is_credit_note = counterpart.move_type in ('out_refund', 'in_refund')

        # Cuenta contable principal de la factura
        invoice_account = move.line_ids.filtered(
            lambda l: l.account_id.account_type in (
                'asset_receivable', 'liability_payable')
        )[:1].account_id

        vals = {
            'move_id': move.id,
            'invoice_date': move.invoice_date,
            'invoice': move.ref or move.name,
            'invoice_ref': invoice_account.id if invoice_account else False,
            'payment_id': counterpart.id,
            'payment_date': event['payment_date'],
            'partner_id': move.partner_id.id,
            'amount': event['paid_amount_company'],
            'amount_currency': event['paid_amount_currency'],
            'currency_rate': event['exchange_rate'],
            'payment_move': counterpart.name,
            'payment_journal_id': counterpart.journal_id.id,
            'reconcile_type': (
                'full' if move.payment_state == 'paid' else 'partial'),
            'payment_type': 'credit_note' if is_credit_note else 'payment',
        }

        # Inicializar columnas de impuestos en cero
        for prefix in set(MAPPED_TAXES.values()):
            vals[prefix + 'base'] = 0.0
            vals[prefix + 'tax'] = 0.0

        # Llenar impuestos desde el breakdown (moneda compañía)
        for tax_data in event['taxes']:
            tax_id = tax_data['tax_id'].id
            prefix = MAPPED_TAXES.get(tax_id)
            if not prefix:
                _logger.warning(
                    "Factura %s: impuesto id=%s (%s) no está en MAPPED_TAXES",
                    move.name, tax_id, tax_data['tax_name'])
                continue
            vals[prefix + 'base'] += tax_data['base_amount_company']
            vals[prefix + 'tax'] += tax_data['tax_amount_company']

        return vals

    def action_customers_suppliers_payments_wizard(self):
        view_id = self.env.ref(
            'customers_suppliers_payments.customers_suppliers_payments_wizard_form').id
        return {
            'type': 'ir.actions.act_window',
            'name': "Create Customers/Suppliers Payments",
            'res_model': 'customers.suppliers.payments.wizard',
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'new',
        }
