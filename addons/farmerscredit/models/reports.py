from odoo import models, fields, api

class AccountMove(models.Model):
    _inherit = 'account.move'


class InvoiceDebtVoucher(models.AbstractModel):
    _name = 'report.farmerscredit.invoice_debt_voucher'

    def _get_report_values(self, docids, data=None):
        report_obj = self.env['ir.actions.report']
        report = report_obj._get_report_from_name('farmerscredit.invoice_debt_voucher')
        
        return {
            'doc_ids': docids,
            'doc_model': self.env['account.move'],
            'docs': self.env['account.move'].browse(docids)
        }