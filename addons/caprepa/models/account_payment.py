# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def action_post(self):

        if self.x_need_approval and self.x_review_result  != 'approved':
            return False
        
        return super(AccountPayment, self).action_post()
    
    # state = fields.Selection(
    #     selection=[
    #         ('draft', 'Draft'),
    #         ('posted', 'Posted'),
    #         ('cancel', 'Cancelled'),
    #     ],
    #     string='Status',
    #     required=True,
    #     readonly=True,
    #     copy=False,
    #     tracking=True,
    #     default='draft',
    # )