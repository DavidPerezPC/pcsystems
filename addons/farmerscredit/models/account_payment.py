# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class AccountPayment(models.Model):
    _inherit = ['account.payment']

    request_id = fields.Many2one(
        'farmerscredit.credit.request',
        string="Contract",
        help="Contract's transfer to loan (created on behalf this credit Contract)",
        domain="[('partner_id', '=', partner_id)]"
    )