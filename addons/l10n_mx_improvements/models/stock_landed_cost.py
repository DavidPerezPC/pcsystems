# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.addons.l10n_mx_edi_extended.models.account_move import CUSTOM_NUMBERS_PATTERN


class StockLandedCost(models.Model):
    _inherit = 'stock.landed.cost'

    customs_date = fields.Date(
        string="Customs Date",
        help="Date the this purchase was processed by Customs", 
        copy=False
    )

    customs_name = fields.Selection(
        [('01', 'Reynosa'),
         ('02', 'Tijuana'),
         ('03', 'Veracruz'),
         ('04', 'AICM'),
        ]
    )
    