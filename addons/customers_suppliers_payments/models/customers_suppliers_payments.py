# -*- coding: utf-8 -*-

from odoo import models, fields, api
MAPPES_TAXS = { 
    24: 'iva_8_',
    25: 'ret_isr_hon_',
    26: 'ret_iva_hon_',
    36: 'ret_iva_hon_',
    28: 'ret_isr_125_',
    29: 'ret_iva_arr_',
    34: 'ret_iva_arr_',
    35: 'ret_iva_arr_',
    30: 'iva_0_',
    31: 'ret_iva_4_',
    33: 'iva_exento_',
    37: 'iva_16_',
    38: 'ieps_6_',
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
    amount = fields.Monetary(string='Payment Amount', readonly=True)
    amount_currency = fields.Monetary(string='Payment Amount Currency', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', related='payment_id.currency_id', readonly=True)
    currency_rate = fields.Float(string='Currency Rate', compute="_compute_currency_rate", readonly=True)
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

###DEFINICION DE IMPUESTOS POR GRUPO DE IMPUESTOS, ESTO TENDRÁ QUE CAMBIAR POR CLIENTE
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
###FIN DEFINICION DE IMPUESTOS POR GRUPO DE IMPUESTOS,
    @api.depends('move_id.amount_total_signed', 'move_id.amount_total_in_currency_signed')
    def _compute_invoice_amount(self):
        for record in self:
            if record.move_id.company_id.currency_id.id != record.move_id.currency_id.id:
                record.invoice_amount_currency = abs(record.move_id.amount_total_in_currency_signed)
                record.invoice_amount = abs(record.move_id.amount_total_signed)
            else:
                record.invoice_amount_currency =  0 
                record.invoice_amount = abs(record.move_id.amount_total_signed)

    @api.depends('amount', 'amount_currency')
    def _compute_currency_rate(self):
        for record in self:
            if record.currency_id and record.amount_currency:
                record.currency_rate = record.amount / record.amount_currency
            else:
                record.currency_rate = 1.0


    def get_all_reconciled_payments(self, start_date, end_date):
        results = []

        # Validate date range
        if not start_date or not end_date:
            raise ValueError("Start date and end date must be provided.")
        if start_date > end_date:
            raise ValueError("Start date cannot be after end date.")
        
        # Step 1: Delete records within this date range 
        self.env['customers.suppliers.payments'].search([
            ('payment_date', '>=', start_date),
            ('payment_date', '<=', end_date)
        ]).unlink()
        
        # Step 2: All reconciled move lines in date range from payments or credit notes
        move_lines = self.env['account.move.line'].search([
            ('date', '>=', start_date),
            ('date', '<=', end_date),
            #("partner_id", "in", [8015]), #[8363, 12234, 9924]),
            ('journal_id.type', 'in', ['bank', 'cash', 'purchase', 'sale']),
            ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']),
            ('move_id.move_type', 'in', ['entry', 'out_refund', 'in_refund']),
            #('move_id.id', 'in', [77436,79352,79426]),
        ])
        

        for line in move_lines:
            #Determine if the move is an invoice
            move_type = line.move_id.move_type
            if move_type in ['out_invoice', 'in_invoice']:
                # It's an invoice, skip
                continue

            # Determine if it's a credit note
            is_credit_note = move_type in ['out_refund', 'in_refund']

            # Gather reconciled invoice lines
            full_lines = line.full_reconcile_id.reconciled_line_ids if line.full_reconcile_id else self.env['account.move.line']
            partial_lines = line.matched_debit_ids.mapped('credit_move_id') + \
                            line.matched_credit_ids.mapped('debit_move_id') + \
                            line.matched_debit_ids.mapped('debit_move_id') + \
                            line.matched_credit_ids.mapped('credit_move_id')

            reconciled_lines = (full_lines | partial_lines).filtered(
                lambda l: l.move_id.move_type in ['out_invoice', 'in_invoice']
            )

            invoices = [x.move_id for x in reconciled_lines]
            for invoice in invoices:
                if abs(line.balance) <= 1:
                    continue
                #invoice = invoice_line.move_id
                #taxes2 = self.get_invoices_taxes(invoice)
                #bases, taxes = invoice._get_rounded_base_and_tax_lines(False()
                result = {
                    'move_id': invoice.id,
                    'invoice_date': invoice.date,
                    'invoice': invoice.ref or invoice.name,
                    'invoice_ref': invoice.line_ids[0].account_id.id,
                    'payment_id': line.move_id.id,
                    'payment_date': line.date,
                    'partner_id': line.partner_id.id,
                    'amount': abs(line.balance),
                    'amount_currency': abs(line.amount_currency or line.balance),
                    'currency_id': line.currency_id.id or line.company_currency_id.id,
                    'payment_move': line.move_id.name,
                    'payment_journal_id': line.move_id.journal_id.id,
                    'reconcile_type': 'full' if line.full_reconcile_id else 'partial',
                    'payment_type': 'credit_note' if is_credit_note else 'payment',
                }               
                tax_totals = invoice.tax_totals['subtotals'] if invoice.tax_totals else []
                percent_paid = abs(line.amount_currency) / invoice.amount_total if invoice.amount_total else 0
                currency_rate = (line.balance / line.amount_currency) if line.amount_currency else 1
                for tax in tax_totals:
                    for tax_group in tax['tax_groups']:
                        tax_affected = MAPPES_TAXS.get(tax_group['id'])
                        if not tax_affected:
                            continue
                        if tax_affected:
                            factor = -1 if is_credit_note else 1
                            #need to multiply by percent paid
                            taxinvolved = self.env['account.tax'].browse(tax_group['involved_tax_ids'][0])
                            tax_percent = taxinvolved.amount / 100
                            results_key_base = f"{tax_affected}base"
                            results_key_tax = f"{tax_affected}tax"
                            result.update({results_key_base: tax_group['base_amount'] * percent_paid * factor,
                                            results_key_tax: tax_group['base_amount'] * tax_percent * percent_paid * factor
                                          })
                results.append(result)

        if results:
            # Create records in the model
            for payment in results:
                self.create(payment)

        return results

    def get_invoices_taxes(self, move_id):

        taxes = {}
        for line in move_id.invoice_line_ids:
            for tax in line.tax_ids:
                tax_amount = 0.0
                tax_base_amount = 0.0
                # Find the tax line for this tax and invoice line
                for tax_line in move_id.line_ids.filtered(lambda l: l.tax_line_id.l10n_mx_tax_type == tax.l10n_mx_tax_type and l.tax_line_id.id == tax.id):
                    tax_amount += abs(tax_line.balance or (tax_line.debit - tax_line.credit))
                    tax_base_amount += abs(tax_line.tax_base_amount)
                # Check if the tax type already exists in the dictionary 
                if tax.l10n_mx_tax_type in taxes:
                    if tax.name not in taxes[tax.l10n_mx_tax_type]['tax_name']:
                        # Append the tax name if it's not already in the list
                        taxes[tax.l10n_mx_tax_type]['tax_name'].append(","+tax.name)
                    taxes[tax.l10n_mx_tax_type]['tax_amount'] += tax_amount
                    taxes[tax.l10n_mx_tax_type]['tax_base_amount'] += tax_base_amount
                else:
                    # Initialize the tax entry if it doesn't exist
                    taxes[tax.l10n_mx_tax_type] = {
                        'tax_name': [tax.name],
                        'tax_amount': tax_amount,
                        'tax_base_amount': tax_base_amount,
                        'is_retention': tax.amount < 0,
                        'account_id': tax.cash_basis_transition_account_id.id,
                        'origin_move_id': move_id.id,
                    }
        # Convert the dictionary to a list of dictionaries
        return taxes
    
    def action_customers_suppliers_payments_wizard(self):
        view_id = self.env.ref('customers_suppliers_payments.customers_suppliers_payments_wizard_form').id
        action =  {
            'type': 'ir.actions.act_window',
            'name': "Create Customers/Suppliers Payments",
            'res_model': 'customers.suppliers.payments.wizard',
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'new',
        }
        return action   
    
    