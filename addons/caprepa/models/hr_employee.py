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
