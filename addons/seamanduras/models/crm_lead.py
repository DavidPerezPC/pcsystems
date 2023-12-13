# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import date

class Lead(models.Model):
    _inherit = ['crm.lead']
   
    assignment_folio = fields.Char(
        string="Folio", 
        help="Enter the Assignment folio for this credit", 
        size=20)

    excutive_id = fields.Many2one(
        'res.partner', string='Executive', check_company=True, index=True, tracking=10,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="Executive that will do the follow up for this credit.")

    payment_term_id = fields.Many2one(
        'account.payment.term', string='Term', 
        check_company=True, 
        tracking=10,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="Term in months for this credit.")

    requested_amount = fields.Monetary(
        string='Requested Amount', 
        help="Requeted Amount for this credit.",
        currency_field='company_currency', 
        tracking=True)

