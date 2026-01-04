from odoo import models, api

class ReportPaymentUtils(models.AbstractModel):
    _name = 'report.payment.utils'
    _description = 'Comprehensive Reconciled Payment Report (incl. Credit Notes)'

    @api.model
    def get_all_reconciled_payments(self, start_date, end_date):
        results = []

        # Step 1: All reconciled move lines in date range from payments or credit notes
        move_lines = self.env['account.move.line'].search([
            ('date', '>=', start_date),
            ('date', '<=', end_date),
            ('reconciled', '=', True),
            ('account_id.internal_type', 'in', ['receivable', 'payable']),
            ('move_id.move_type', 'in', ['entry', 'out_refund', 'in_refund']),
        ])

        for line in move_lines:
            # Determine if it's a credit note
            move_type = line.move_id.move_type
            is_credit_note = move_type in ['out_refund', 'in_refund']

            # Gather reconciled invoice lines
            full_lines = line.full_reconcile_id.line_ids if line.full_reconcile_id else self.env['account.move.line']
            partial_lines = line.matched_debit_ids.mapped('credit_move_id') + \
                            line.matched_credit_ids.mapped('debit_move_id')

            reconciled_lines = (full_lines | partial_lines).filtered(
                lambda l: l.move_id.move_type in ['out_invoice', 'in_invoice']
            )

            for invoice_line in reconciled_lines:
                invoice = invoice_line.move_id
                results.append({
                    'payment_date': line.date,
                    'invoice': invoice.name,
                    'partner': line.partner_id.name,
                    'amount': abs(line.amount_currency or line.balance),
                    'currency': line.currency_id.name or line.company_currency_id.name,
                    'payment_move': line.move_id.name,
                    'payment_journal': line.move_id.journal_id.name,
                    'reconcile_type': 'full' if line.full_reconcile_id else 'partial',
                    'payment_type': 'credit_note' if is_credit_note else 'payment',
                })

        return results
