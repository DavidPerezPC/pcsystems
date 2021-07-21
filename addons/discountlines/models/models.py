# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare

ACCOUNTS_ = {2: {'SALES': 127, 'DISCOUNT': 503}}

class AccountMove(models.Model):
    _inherit = 'account.move'

    def get_additional_entries(self, line):

        discount_amount = (line.price_unit * line.quantity)-(line.price_subtotal)
        sales_move = {
            'product_id': line.product_id.id,
            'exclude_from_invoice_tab': True,
            'is_discount_line': True,
            'move_id': line.move_id.id,
            'company_id': line.company_id.id,
            'credit': discount_amount,
            'analytic_tag_ids': [6, 0, line.analytic_tag_ids.ids] if line.analytic_tag_ids else False,
            'analytic_account_id': line.analytic_account_id,
            'account_id': ACCOUNTS_[line.company_id.id]['SALES'],
            'name': line.name,
        }
        discount_move = {**sales_move}
        discount_move.update({'account_id':  ACCOUNTS_[line.company_id.id]['DISCOUNT'],
                              'credit': False,
                              'debit': discount_amount
                              })

        return [sales_move, discount_move]

    def button_draft(self):

        res = super(AccountMove, self).button_draft()
        self.mapped('line_ids').filtered(lambda line: line.is_discount_line).unlink()

        return res

    def action_post(self):

        ml = self.env['account.move.line']
        lines = self.mapped('line_ids').filtered(lambda l: l.discount > 0)
        for line in lines:
            for move in self.get_additional_entries(line):
                ml.with_context(check_move_validity=False).create(move)
        res = super(AccountMove, self).action_post()

        return res


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    is_discount_line = fields.Boolean(string="True if this move line is created from a discount line",
                                      default=False)

# class credits(models.Model):
#     _name = 'credits.credits'
#     _description = 'credits.credits'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100
