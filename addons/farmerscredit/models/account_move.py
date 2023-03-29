# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class AccountMove(models.Model):
    _inherit = ['account.move']

    request_id = fields.Many2one(
        'farmerscredit.credit.request',
        string="Contract",
        help="Contract's Invoice (created on behalf this credit Contract)",
        domain="[('partner_id', '=', partner_id)]"
    )