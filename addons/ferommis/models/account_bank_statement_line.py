# -*- coding: utf-8 -*-

from odoo import models, fields

class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    def _thread_to_store(self, store: object, /, *, fields=None, request_list=None):
        pass