# -*- coding: utf-8 -*-

from odoo import models, fields, tools, api, _
from datetime import datetime, timedelta
from urllib.parse import quote_plus 
from odoo.addons.base.models.ir_ui_view import keep_query

TAXES_IDS = [126,127]
ACC_TAX_ID = 69
TAX_RATE = 0.16
TAX_LABELS = ['IVA(12%) GASTOS', 'IVA(5.33%) GASTOS']

class AccountMove(models.Model):
    _inherit = ['account.move']
    
    update_tax_base_needed = fields.Boolean(
        compute='_compute_update_tax_base_needed',
        inverse='_inverse_update_tax_base_needed',
        store=True,
    )

    @api.depends('tax_cash_basis_created_move_ids','move_type', 'payment_id', 'payment_state', 'statement_line_id')
    def _compute_update_tax_base_needed(self):
        """ Check whatever or not the base of the invoice needs to be changed.
        """
        for move in self:
            move.update_tax_base_needed = \
                move.move_type in ['in_invoice', 'in_refund'] \
                and move.tax_cash_basis_created_move_ids \
                and (TAXES_IDS[0] in move.invoice_line_ids.tax_ids.ids
                     or TAXES_IDS[1] in move.invoice_line_ids.tax_ids.ids)
    
    def _inverse_update_tax_base_needed(self):

        for move in self:
            move.update_tax_base_needed = move.tax_cash_basis_created_move_ids \
                and (TAXES_IDS[0] in move.invoice_line_ids.tax_ids.ids
                     or TAXES_IDS[1] in move.invoice_line_ids.tax_ids.ids)
                
    def update_cash_base_payment(self):
        
        cmonto = ''
        for inv in self:
            if inv.move_type not in ['in_invoice', 'in_refund']:
                continue
            line = inv.invoice_line_ids.filtered(lambda il: 
                        TAXES_IDS[0] in il.tax_ids.ids 
                     or TAXES_IDS[1] in il.tax_ids.ids)
            if not line:
                continue
            base_ori = line.price_subtotal
            for moves in inv.tax_cash_basis_created_move_ids:
                for move in moves:
                    line = move.line_ids.filtered(lambda m: m.account_id.id == ACC_TAX_ID and m.name in TAX_LABELS)
                    new_base_amount = line.debit or line.credit or 0
                    new_base_amount = new_base_amount/ TAX_RATE
                    acc_id = line.company_id.account_cash_basis_base_account_id.id
                    base_ml_ids = move.line_ids.filtered(lambda acc: 
                        (acc.account_id.id == acc_id and acc.debit + acc.credit == base_ori) 
                                                )
                    sql = f"update account_move_line set tax_base_amount = {new_base_amount} where id = {line.id};"
                    for ml in base_ml_ids:
                        if ml.debit:
                            sql += f"update account_move_line set debit = {new_base_amount} where id = {ml.id};"
                        else:
                            sql += f"update account_move_line set credit = {new_base_amount} where id = {ml.id};"
                    self.env.cr.execute(sql)
                    cmonto = '{:20,.2f}'.format(new_base_amount).strip()

            if cmonto:
                cmsg = f"El monto base fue actualizado a: {cmonto}"
                ctype = 'success'
            else:
                cmsg = "NO se actualizo ninguna base"
                ctype = 'error'
            notification = {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                'title': _('Monto Base Actualizado'),
                'type': ctype,
                'message': cmsg,
                'sticky': True,
                            }
                }
            return notification

            

# class MailTemplate(models.Model):
#     "Templates for sending email"
#     _inherit = "mail.template"
 
#     def send_mail(self, res_id):
        
#         res_id = super(MailTemplate, self).send_mail(res_id)

#         return res_id
# class MailComposeMessage(models.TransientModel):
#     _inherit = 'mail.compose.message'

#     def get_mail_values(self, res_ids):
#         """ Override method to link mail automation activity with mail statistics"""
#         res = super(MailComposeMessage, self).get_mail_values(res_ids)

#         return res
