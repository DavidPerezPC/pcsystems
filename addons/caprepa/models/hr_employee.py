# -*- coding: utf-8 -*-

from odoo import models, fields, api

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    admission_date = fields.Date(
        string="Admission Date",
        help="Select or enter Date of Admission for this Employee"
    )

    recruiter_id = fields.Many2one(
        comodel_name='res.users',
        string="Recruiter",
        help="Select the Recruiter for this Employee",
        tracking=1,
        domain="[('share', '=', False), ('company_ids', 'in', company_id)]"
        )   
     
    source_id = fields.Many2one(
        comodel_name='utm.source',
        string="Source",
        help="Recruitment Source for this Employee",
        )   

    medium_id = fields.Many2one(
        comodel_name='utm.medium',
        string="Mediums",
        help="Recruitment Medium for this Employee",
        )
    
    driver_license = fields.Char(
        string="License",
        help="Driver License number"
    )

    license_expires = fields.Date(
        string="Expires on",
        help="Driver License expiration date"
    )
    
    mx_clabe = fields.Char(
        string="CLABE",
        help="18 digit account number for this account (CLABE at Mexico)",
        related='bank_account_id.l10n_mx_edi_clabe',
        readonly=True,
        size=18,
    )

    salary_daily = fields.Float(
        string='Daily Salary',
        help='Daily Salary for this Employee',
        digits=(10,2)
    )
        
    salary_base = fields.Float(
        string='Base Salary',
        help='Base Salary for this Employee',
        digits=(10,2)
    )
# class caprepa(models.Model):
#     _name = 'caprepa.caprepa'
#     _description = 'caprepa.caprepa'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100
