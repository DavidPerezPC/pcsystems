# -*- coding: utf-8 -*-

from odoo import models, fields, tools, api, _
from datetime import datetime, timedelta
from urllib.parse import quote_plus 
from odoo.addons.base.models.ir_ui_view import keep_query


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

    def action_payment_move_send(self):
        """ Opens a wizard to compose an email, with relevant mail template loaded by default """
        self.ensure_one()
        lang = self.env.context.get('lang')
        mail_template = self._find_payment_mail_template()
        if mail_template and mail_template.lang:
            lang = mail_template._render_lang(self.statement_line_id.ids)[self.statement_line_id.id]
        ctx = {
            'default_model': 'account.bank.statement.line',
            'default_res_id': self.statement_line_id.id,
            'default_use_template': bool(mail_template),
            'default_template_id': mail_template.id if mail_template else None,
            'default_attachment_ids': [(6,0,self.statement_line_id.attachment_ids.ids)],
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
