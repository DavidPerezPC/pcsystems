# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class SaleReport(models.Model):
    _inherit = "sale.report"

    province_id = fields.Many2one('res.country.state', 'Province', readonly=True)

    def _select_additional_fields(self):
        res = super()._select_additional_fields()
        res['province_id'] = "partner.state_id"
        return res

    def _group_by_sale(self):
        res = super()._group_by_sale()
        res += """,
            partner.state_id """
        return res
