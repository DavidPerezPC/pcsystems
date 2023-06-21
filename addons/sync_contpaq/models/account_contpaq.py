# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class AccountContpaq(models.Model):
    _name = 'sync.contpaq.account'
    _description = 'Relación de Cuentas Contpaq con Odoo'

    code = fields.Char(
        string="Code",
        help="Contpaq Account to be redirected to Odoo Account",
        required=True,
        index=True,
    )

    name = fields.Char(
        string="Name",
        help="Contpaq Account Name"
    )

    account_id = fields.Many2one(
        comodel_name='account.account',
        string='Odoo Acc.',
        help='Equivalent Odoo Account for the Contpaq Account',
        store=True, readonly=False,
        index=True,
        auto_join=True,
        ondelete="cascade",
        domain="[('deprecated', '=', False), ('company_id', '=', company_id), ('is_off_balance', '=', False)]",
        check_company=True,
        tracking=True,
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        help="Company in Odoo that will use this Account",
        required=True,
        default=lambda self: self.env.company,
        index=True
    )

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Partner",
        help="Select partner that uses this Odoo Account, leave blank if is not needed",
        readonly=False, index=True,
        domain="[('company_id', 'in', (False, company_id))]")  
    
    analytic_account_id = fields.Many2one(
        comodel_name='account.analytic.account',
        string="Analytic Account",
        copy=False, check_company=True,  # Unrequired company
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")

