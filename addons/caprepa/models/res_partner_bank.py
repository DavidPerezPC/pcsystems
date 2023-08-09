# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.image import image_data_uri


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    mx_clabe = fields.Char(
        string="CLABE",
        help="Enter the 18 digit account number for this account (CLABE at Mexico)",
        size=18,
    )


class ResBank(models.Model):
    _inherit = 'res.bank'

    abm_code = fields.Char(
        string="ABM Code",
        help="Enter the three digit code for this Bank at Mexico, assigned by ABM",
        size=3,
    )