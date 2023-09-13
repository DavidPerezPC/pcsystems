# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    expense_flow_id  = fields.Many2one(
        comodel_name='caprepa.expenses.flow', 
        string="Expense",
        help="Expense where this Invoice was used",
    )
