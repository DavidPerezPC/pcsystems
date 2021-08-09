# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountMoveLine(models.Model):
    _inherit =  "account.move.line"

    @api.depends('product_id', 'account_id', 'partner_id', 'date')
    def _compute_analytic_account(self):
        for record in self:
            if not record.exclude_from_invoice_tab or not record.move_id.is_invoice(include_receipts=True):
                rec = self.env['account.analytic.default'].account_get(
                    product_id=record.product_id.id,
                    partner_id=record.partner_id.commercial_partner_id.id or record.move_id.partner_id.commercial_partner_id.id,
                    account_id=record.account_id.id,
                    user_id=record.move_id.invoice_user_id.id or record.env.uid,
                    date=record.date,
                    company_id=record.move_id.company_id.id
                )
                if rec:
                    record.analytic_account_id = rec.analytic_id
                    record.analytic_tag_ids = rec.analytic_tag_ids


class AccountAnalyticDefault(models.Model):
    _inherit  = "account.analytic.default"

    product_categ_id = fields.Many2one('product.category', string='Product Category', ondelete='cascade', help="Select product category to consider all the productos that belongs to this category in analytic default.") 

    @api.model
    def account_get(self, product_id=None, partner_id=None, account_id=None, user_id=None, date=None, company_id=None):
        domain = []
        categ = False
        if product_id:
            product_model = self.env['product.product']
            product_object = product_model.browse(product_id)
            categ=product_object.categ_id
            domain += ['|', ('product_categ_id', '=', categ.id)]
        domain += [('product_categ_id','=', False)]
        if product_id:
            domain += ['|', ('product_id', '=', product_id)]
        domain += [('product_id', '=', False)]
        if partner_id:
            domain += ['|', ('partner_id', '=', partner_id)]
        domain += [('partner_id', '=', False)]
        if account_id:
            domain += ['|', ('account_id', '=', account_id)]
        domain += [('account_id', '=', False)]
        if company_id:
            domain += ['|', ('company_id', '=', company_id)]
        domain += [('company_id', '=', False)]
        if user_id:
            domain += ['|', ('user_id', '=', user_id)]
        domain += [('user_id', '=', False)]
        if date:
            domain += ['|', ('date_start', '<=', date), ('date_start', '=', False)]
            domain += ['|', ('date_stop', '>=', date), ('date_stop', '=', False)]
        best_index = -1
        res = self.env['account.analytic.default']
        for rec in self.search(domain):
            index = 0
            if categ and rec.product_id:
                if rec.product_id.categ_id == categ:
                    index +=1
            if rec.product_id: index += 1
            if rec.partner_id: index += 1
            if rec.account_id: index += 1
            if rec.company_id: index += 1
            if rec.user_id: index += 1
            if rec.date_start: index += 1
            if rec.date_stop: index += 1
            if index > best_index:
                res = rec
                best_index = index
        return res


