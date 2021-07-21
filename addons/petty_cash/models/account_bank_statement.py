# -*- coding: utf-8 -*-

from odoo import models, fields, api

PETTY_CASH_ACCOUNTS_PREFIX = '_petty.cash%'

class AccountBankStatement(models.Model):
    _inherit = "account.bank.statement"

    @api.model
    @api.depends('is_petty_cash', 'journal_id')
    def _get_is_petty_cash(self):
        petty_cash_account_ids = self._get_petty_cash_account_ids()
        for rec in self:
            rec.is_petty_cash = rec.journal_id.default_account_id.id in petty_cash_account_ids

        return

    def _get_petty_cash_account_ids(self):
        search_domain = str(self.env.company.id).strip()
        search_domain += PETTY_CASH_ACCOUNTS_PREFIX
        acc_ids = self.env['ir.config_parameter'].search([('key', '=like', search_domain)])
        account_ids = [int(x['value']) for x in acc_ids]

        return account_ids

    payment_id = fields.Many2one(
        'account.payment',
        string="Petty Cash Payment",
        help="Payment related to this Petty Cash",
        copy=False
    )

    is_petty_cash = fields.Boolean(
        compute="_get_is_petty_cash", store=False,
        help="Internal helper to know if destination account is petty cash"
    )

    @api.onchange('journal_id')
    def onchange_journal_id(self):
        domain = {'payment_id': [('destination_account_id.id', '=', self.account_id.id),
                                 ('petty_cash_concilied', '!=', True)]}
        return {'domain': domain}

    def button_validate_or_action(self):

        res = super(AccountBankStatement, self).button_validate_or_action()
        reconcile_ids = self.payment_id.move_id.mapped('line_ids').filtered(lambda l: l.account_id == self.account_id)
        for line in self.line_ids:
            ltoreconcile = line.move_id.mapped('line_ids').filtered(lambda l: l.account_id == self.account_id)
            ltoreconcile.write({'partner_id': self.payment_id.partner_id.id})
            reconcile_ids += ltoreconcile

        reconcile_ids.reconcile()
        self.payment_id.write({'petty_cash_concilied': True})

        return res

    def button_reprocess(self):

        res = super(AccountBankStatement, self).button_reprocess()
        reconcile_ids = self.payment_id.move_id.mapped('line_ids').filtered(lambda l: l.account_id == self.account_id)
        for line in self.line_ids:
            ltoreconcile = line.move_id.mapped('line_ids').filtered(lambda l: l.account_id == self.account_id)
            reconcile_ids += ltoreconcile

        reconcile_ids.remove_move_reconcile()
        self.payment_id.write({'petty_cash_concilied': False})

        return res




