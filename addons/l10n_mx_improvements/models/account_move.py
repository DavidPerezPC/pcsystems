# -*- coding: utf-8 -*-

from odoo import models, fields, tools, api, _
from datetime import datetime, timedelta
from urllib.parse import quote_plus 
#from odoo.addons.base.models.ir_ui_view import keep_query
from odoo.addons.base.models.ir_qweb import keep_query
import base64

class AccountMove(models.Model):
    _inherit = ['account.move']

    # @api.onchange('partner_id')
    # def _onchange_partner_id(self):
    #     res = super(AccountMove, self)._onchange_partner_id()
    #     for move in self:
    #         if move.partner_id:
    #             move.l10n_mx_edi_usage = move.partner_id.l10n_mx_edi_usage
    #             move.l10n_mx_edi_payment_method_id = move.partner_id.l10n_mx_edi_payment_method_id.id

    #     return res
    payment_receipt_title = fields.Char(
            compute='_compute_payment_receipt_title', store=False
        )
    
    partner_type = fields.Char(default='customer', store=False)
    amount = fields.Monetary(store=False)
    memo = fields.Char(store=False)

    def _compute_payment_receipt_title(self):
        for move in self:
            move.payment_receipt_title = _('Recibo de Pago')

    def _get_payment_receipt_report_values(self):
        # EXTENDS 'account'
        values = {
            'display_invoices': True,
            'display_payment_method': True,
        }

        cfdi_infos = self.id and self._l10n_mx_edi_get_extra_payment_report_values()
        if cfdi_infos:
            values.update({
                'display_invoices': False,
                'display_payment_method': False,
                'cfdi': cfdi_infos,
            })

        return values
    
    def _get_payment(self):
        payment_id = self.id
        memo = ''
        for line in self.line_ids:
            if line.account_id.account_type == 'asset_receivable':
                memo += line.name.strip() + ', '
        self.memo = f"Pago Factura(s): {memo[:-2]}"
        self.amount = self.statement_line_id.amount
        payment_report = self.env.ref('l10n_mx_improvements.action_report_payment_statement_receipt')
        data_record = base64.b64encode(
            self.env['ir.actions.report'].sudo()._render_qweb_pdf(
                payment_report, [payment_id], data=None)[0])
        ir_values = {
            'name': f"{self.payment_receipt_title.replace(' ', '_')}_{self.name}.pdf",
            'type': 'binary',
            'datas': data_record,
            'store_fname': data_record,
            'mimetype': 'application/pdf',
            'res_model': 'account.move',
            'res_id': self.id,
            'description': f"PDF del CFDI {self.name}",
        }
        payment_report_attachment_id = self.env['ir.attachment'].sudo().create(ir_values)
        if payment_report_attachment_id:
            return payment_report_attachment_id
        return False
            # email_template = self.env.ref(
            #     'email_attachments.email_template_invoice_report')
            # if self.partner_id.email:
            #     email = self.partner_id.email
            # else:
            #     email = 'admin@example.com'
            # if email_template and email:
            #     email_values = {
            #         'email_to': email,
            #         'email_cc': False,
            #         'scheduled_date': False,
            #         'recipient_ids': [],
            #         'partner_ids': [],
            #         'auto_delete': True,
            #     }
            #     email_template.attachment_ids = [
            #         (4, invoice_report_attachment_id.id)]
            #     email_template.with_context(partner=self.partner_id,
            #                                 inv=self).send_mail(
            #         self.id, email_values=email_values, force_send=True)
            #     email_template.attachment_ids = [(5, 0, 0)]

    def action_payment_move_send(self):
        """ Opens a wizard to compose an email, with relevant mail template loaded by default """
        self.ensure_one()
        lang = self.env.context.get('lang')
        attach_ids = self.attachment_ids
        report_payment = attach_ids.filtered(lambda att: att.name == f"{self.payment_receipt_title.replace(' ', '_')}_{self.name}.pdf")
        attach_ids = self.attachment_ids.ids
        if not report_payment:
            report_payment = self._get_payment()
            if report_payment:
                attach_ids.append(report_payment.id)
        mail_template = self._find_payment_mail_template()
        if mail_template and mail_template.lang:
            lang = mail_template._render_lang(self.statement_line_id.ids)[self.statement_line_id.id]
        ctx = {
            'default_model': 'account.bank.statement.line',
            'default_res_ids': [self.statement_line_id.id],
            'default_use_template': bool(mail_template),
            'default_template_id': mail_template.id if mail_template else None,
            'default_attachment_ids': [(6,0,attach_ids)],
            'default_composition_mode': 'comment',
            'proforma': self.env.context.get('proforma', False),
            'force_email': True,
            'model_description': self.with_context(lang=lang).type_name,
        }
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'view_id': False,
            'target': 'new',
            'context': ctx,
        }
# l10n_mx_edi.report_payment_receipt
    def _find_payment_mail_template(self):
        #mail_tmpl = self.env['mail.template'].search([('name','=','mail_template_move_payment'),
        #                                                ('module')])
        mail_tmpl = self.env.ref('l10n_mx_improvements.mail_template_move_payment', raise_if_not_found=False)
        
        return mail_tmpl
    
    def update_cash_base_payment(self):

        for inv in self:
            if inv.move_type != 'in_invoice' and inv.amount_untaxed != 0.01:
                continue

            if len(inv.invoice_line_ids) > 1 or len(inv.invoice_line_ids[0].tax_ids) > 1:
                raise UserWarning("Factura con mas de un artículo y/o con mas de un impuesto.")
                return 
            tax = inv.invoice_line_ids[0].tax_ids[0].amount / 100
            new_base_amount = inv.amount_tax / tax
            acc_id = inv.company_id.account_cash_basis_base_account_id.id
#            base_ml_ids = inv.tax_cash_basis_created_move_ids[0].line_ids.filtered(lambda acc: acc.account_id.id == acc_id )
            base_ml_ids = inv.tax_cash_basis_created_move_ids
            reversed_ids = [x for x in base_ml_ids['reversed_entry_id'].ids]
            sql = ""
            for mov in base_ml_ids:
                if sql != "":
                    break
                if mov.reversed_entry_id.id or mov.id in reversed_ids:
                    continue
                for ml in mov.line_ids.filtered(lambda acc: acc.account_id.id == acc_id):
                    if ml.debit:
                        sql += f"update account_move_line set debit = {new_base_amount}, balance = {new_base_amount} where id = {ml.id};"
                    else:
                        sql += f"update account_move_line set credit = {new_base_amount}, balance = {-new_base_amount} where id = {ml.id};"
            self.env.cr.execute(sql)
            cmonto = '{:20,.2f}'.format(new_base_amount).strip()
            notification = {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Monto Base Actualizado'),
                    'type': 'success',
                    'message': f"El monto base fue actualizado a: {cmonto}",
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
