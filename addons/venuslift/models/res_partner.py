# -*- coding: utf-8 -*-

from odoo import models, fields, api

class Partner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def default_get(self, fields):
        res = super(Partner, self).default_get(fields)
        res.update({ 'company_id': self.env.company.id} ) 

        return res   

    