# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime, timedelta

class AccountMove(models.Model):
    _inherit = ['account.move']

    def fix_post_time(self):

        for move in self:
            move.l10n_mx_edi_post_time = move.l10n_mx_edi_post_time - timedelta(hours=1)

    