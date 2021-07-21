# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.tools.safe_eval import json

PETTY_CASH_ACCOUNTS_PREFIX = '_petty.cash%'


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    @api.model
    @api.depends('is_petty_cash_account', 'destination_account_id')
    def _get_is_petty_cash(self):

        petty_cash_account_ids = self._get_petty_cash_account_ids()
        for rec in self:
            rec.is_petty_cash_account = rec.destination_account_id.id in petty_cash_account_ids

        return

    def _get_petty_cash_account_ids(self):

        search_domain = str(self.env.company.id).strip()
        search_domain += PETTY_CASH_ACCOUNTS_PREFIX
        acc_ids = self.env['ir.config_parameter'].search([('key', '=like', search_domain)])
        account_ids = [int(x['value']) for x in acc_ids]

        return account_ids

    def _get_petty_cash_count(self):
        for rec in self:
            rec.petty_cash_count = len(rec.petty_cash_ids)
        return

    def _get_petty_cash_concilied(self):
        return False

    def link_petty_cash(self):
        return True

    petty_cash_ids = fields.One2many(
        'account.bank.statement', 'payment_id',
        domain="[('journal_id.default_account_id', '=', self.destination_account_id)]",
        string="Petty's Cash related to this Payment",
        copy=False
    )

    # petty_cash_domain = fields.Char(
    #     readonly=True, store=False
    #   )

    is_petty_cash_account = fields.Boolean(
        compute="_get_is_petty_cash", store=False,
        help="Internal helper to know if destination account is petty cash"
    )

    petty_cash_concilied = fields.Boolean(
        store=True, default=False,
        string="Internal helper to know if the Payment has beeen attached to the petty cash",
        help="Internal helper to know if the Payment has beeen attached to the petty cash"
    )

    petty_cash_count = fields.Integer(
        compute="_get_petty_cash_count", store=False,
        string="Petty's Cash count",
        help="Indicate the number of Petty's Cash")

    def button_open_petty_cash(self):
        ''' Redirect the user to the petty cash statemnt reconciled to this payment.
        :return:    An action on account.move.
        '''
        self.ensure_one()

        action = {
            'name': _("Petty Cash"),
            'type': 'ir.actions.act_window',
            'res_model': 'account.bank.statement',
            'context': {'search_default_payment_id': self.id,
                        'default_payment_id': self.id},
            'domain': [('payment_id', '=', self.id)],
            'view_mode': 'tree,form',
        }

        return action
