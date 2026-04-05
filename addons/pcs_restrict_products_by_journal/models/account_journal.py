# -*- coding: utf-8 -*-
# Part of PC Systems. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    allowed_product_ids = fields.Many2many('product.product', 
                                           string='Allowed Products'
                                           )

    # @api.model_create_multi
    # def create(self, vals_list):
    #     journal = super(AccountJournal, self).create(vals_list)
    #     for vals in vals_list:
    #         if journal.user_id:
    #             journal.users_ids = [(4, journal.user_id.ids)]
    #             if journal.user_id != self.env.uid and journal not in journal.user_id.journals_ids:
    #                 journal.user_id.journals_ids = [(4, journal.ids)]
    #     return journal

    # def write(self, vals):
    #     res = super(AccountJournal, self).write(vals)
    #     if 'user_id' in vals:
    #         self.users_ids = [(4, vals['user_id'].ids)] if vals.get('user_id') else [(5, 0, 0)]
    #         if self.user_id != self.env.uid and self not in self.user_id.journals_ids:
    #             self.user_id.journals_ids = [(4, self.ids)]
    #     return res

    # @api.depends('user_id')
    # def _onchange_user_id(self):
    #     if self.user_id:
    #         restricted_journals = self.user_id.journals_ids.ids
    #         return {'domain': {'user_id': [('id', '=', self.user_id.id)], 'id': [('id', 'in', restricted_journals)]}}

    # @api.model
    # def search_fetch(self, domain, field_names, offset=0, limit=None, order=None):
    #     domain = domain or []
    #     if self.env.user.has_group('base.group_user') and self.env.user.has_group('bi_restriction_of_journals_for_users.group_access_restrict_journal_features'):
    #         domain += [('users_ids', 'in', self.env.user.id)]

    #     return super(AccountJournal, self).search_fetch(domain, field_names, offset=offset, limit=limit, order=order)
