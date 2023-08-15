# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class AccountMove(models.Model):
    _inherit = 'account.move'

    def button_draft(self):

        ids = str(tuple(self.ids)).replace(",)",")")
        sql = f"update account_move set tax_cash_basis_rec_id = null where id in {ids} and tax_cash_basis_rec_id is not null;"
        sql += f"update account_move set tax_cash_basis_origin_move_id = null where id in {ids} and tax_cash_basis_origin_move_id is not null;"

        self.env.cr.execute(sql)
        return super().button_draft()
    