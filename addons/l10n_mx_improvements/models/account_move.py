# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime, timedelta

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