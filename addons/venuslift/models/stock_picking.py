# -*- coding: utf-8 -*-

from odoo import models, fields, api

class StockPikcing(models.Model):
    _inherit = ['stock.picking']


    payment_term_id = fields.Many2one(
        'account.payment.term', string='Payment Terms', related='sale_id.payment_term_id')
    invoice_payment_state = fields.Selection(related='sale_id.invoice_payment_state', string='Payment State', help='Payment state related to the Sale Order Invoice')


