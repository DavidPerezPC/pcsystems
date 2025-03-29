# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _


class SaleOrder(models.Model):
    _inherit = "sale.order"

    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Warehouse',
        default=False, store=True, readonly=False, required=True,
        check_company=True)
    
    @api.onchange('partner_id')
    def onchange_partner_id(self):
        if self.partner_id:
            self.warehouse_id = False
#        self.warehouse_id = self.env.user.property_warehouse_id

