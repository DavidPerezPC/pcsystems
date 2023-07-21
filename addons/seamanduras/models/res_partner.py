# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import date

class Partner(models.Model):
    _inherit = ['res.partner']
   
    curp = fields.Char(
        string="CURP", 
        help="Enter the Unique Identification Population Key assigned by Goverment", 
        size=18)

    ine = fields.Char(
        string="INE", 
        help="Enter the INE number issued by Goverment", 
        size=14)

    nss = fields.Char(
        string="SSN",
        help="Enter the Social Security Number",
        size=20)

    marital_state = fields.Selection(
        string="Marital State",
        help="Select the marital state",
        selection=[('single', 'Single'),
                    ('conjugal', 'Conjugal Society'),
                    ('separated', 'Separated Goods'),
                    ('widower', 'Widower'),
                    ('divorced', 'Divorced'),
                ])

    birth_date = fields.Date(
        string="Birth Date",
        help="Select or type the birth date"
    )

    age = fields.Integer(
        string="Age",
        help="Calculate age old",
        compute="_get_partner_age",
        store=True
    )

    sex = fields.Selection(
        string="Sex",
        help="Select sex, F=Female or M=Male",
        selection=[('female', 'Female'),
                    ('male', 'Male'),

                ])
    
    has_assignments = fields.Boolean(
        string="Assignments?",
        help="Indicate if has Assignments",
        default=False
    )

    assignment_amount = fields.Float(
        string="Amount",
        help="Enter the assignment amount",
    )

    @api.depends("birth_date")
    def _get_partner_age(self):

        for partner in self:
            birthdate = partner.birth_date
            if not birthdate:
                continue
            today = date.today()
        
            # A bool that represents if today's day/month precedes the birth day/month
            one_or_zero = ((today.month, today.day) < (birthdate.month, birthdate.day))
            
            # Calculate the difference in years from the date object's components
            year_difference = today.year - birthdate.year
            
            # The difference in years is not enough. 
            # To get it right, subtract 1 or 0 based on if today precedes the 
            # birthdate's month/day.
            
            # To do this, subtract the 'one_or_zero' boolean 
            # from 'year_difference'. (This converts
            # True to 1 and False to 0 under the hood.)
            partner.age = year_difference - one_or_zero