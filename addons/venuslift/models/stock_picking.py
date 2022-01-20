# -*- coding: utf-8 -*-

from odoo import models, fields, api

class StockPicking(models.Model):
    _inherit = ['stock.picking']


    payment_term_id = fields.Many2one(
        'account.payment.term', string='Payment Terms', related='sale_id.payment_term_id')
    invoice_payment_state = fields.Selection(related='sale_id.invoice_payment_state', string='Payment State', help='Payment state related to the Sale Order Invoice')
    ready_to_deliver = fields.Boolean(related='sale_id.ready_to_deliver', string = 'To Deliver', help='Indicates if can be delivered')

    @api.depends('state')
    def _compute_show_validate(self):
        super(StockPicking, self)._compute_show_validate()
        for picking in self:
            if picking.show_validate and not picking.ready_to_deliver:
                picking.show_validate = False  
    