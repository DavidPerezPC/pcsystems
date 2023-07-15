# -*- coding: utf-8 -*-

from odoo import models, fields, api

class Partner(models.Model):
    _inherit = ['res.partner']

    @api.model
    def default_get(self, fields):
        res = super(Partner, self).default_get(fields)
        res.update({ 'company_id': self.env.company.id} )         
        
        return res   

    source_id = fields.Many2one('utm.source')
    credit_limit = fields.Float(tracking=True)
    user_id = fields.Many2one('res.users', tracking=True)
    comercial_changed = fields.Boolean(string='Indicates if assigned commercial has changed', store=False, default=False)
    credit_limit_changed = fields.Boolean(string='Indicates if credit limit has changed', store=False, default=False)


   
    # @api.onchange('credit_limit')
    # def credit_limit_onchange(self):
    #     self.credit_limit_changed = True

    def send_mail_to_administrator(self):

        template_id = self.env.ref("venuslift.credit_limit_change_email_template")
        email_template = self.env['mail.template'].browse(template_id.id)
        #email_template.with_context({'lang': 'es_ES', 'template_preview_lang': 'es_ES'}).send_mail(self.ids, force_send=True)
        email_template.send_mail(self.id, force_send=True)

    # @api.onchange('user_id')
    # def user_id_onchange(self):
    #     self.comercial_changed = True
    #     self.send_mail_to_administrator()


