# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from datetime import datetime, timedelta
import locale

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.osv import expression
from odoo.tools import float_is_zero, float_compare, float_round

import phonenumbers

class CreditRequestLine(models.Model):
    _name = 'farmerscredit.credit.request.line'
    _inherit = 'analytic.mixin'
    _description = "Credit Request Line (Crops and Season)"
    _rec_names_search = ['name', 'request_id.name']
    _order = 'request_id, id'
    _check_company_auto = True


    request_id = fields.Many2one(
        comodel_name='farmerscredit.credit.request',
        string="Request Reference",
        required=True, ondelete='cascade', index=True, copy=False)

    # Credit Request-related fields
    company_id = fields.Many2one(
        related='request_id.company_id',
        store=True, index=True, precompute=True)
    partner_id = fields.Many2one(
        related='request_id.partner_id',
        string="Applicant",
        store=True, index=True, precompute=True)
    salesman_id = fields.Many2one(
        related='request_id.user_id',
        string="Salesperson",
        store=True, precompute=True)
    state = fields.Selection(
        related='request_id.state',
        string="Request Status",
        copy=False, store=True, precompute=True)
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        related='request_id.currency_id',
        string="Currency",
        help="Credit's Request Currency"
    )

    # Generic configuration fields
    crop_id = fields.Many2one(
        comodel_name='farmerscredit.crops',
        string="Crop",
        required=True, readonly=False, change_default=True, index=True,
        )

    season_id = fields.Many2one(
        comodel_name='farmerscredit.seasons',
        string="Season",
        required=True, readonly=False, change_default=True, index=True,
        )
    
    season_crop_info_id = fields.Many2one(
        "farmerscredit.season.crop.info",
        string="Season/Crop Info",
    )

    name = fields.Char(
        string="Description",
        store=True, readonly=False )

    credit_per_unit = fields.Float(
        string="Credit",
        help="Credit Amount per Hectare for this Crop in this Season",
        digits=(10,2)
    )

    quota_per_unit = fields.Float(
        string="Quota",
        help="Quota Amount per Hectare for this Crop in this Season",
        digits=(10,2)
    )

    area = fields.Float(
        string="Area",
        help="Enter total area for this Crop",
        digits=(10,2)
    )

    credit_amount = fields.Monetary(
        string="Amount",
        help="Credit amount given for this crop",
        compute="_compute_amounts", store=True, readonly=True,
    )


    @api.onchange('crop_id')
    def _onchange_crop_id(self):
        for rec in self:
            if not rec.season_id and \
                (rec.credit_per_unit or rec.quota_per_unit):
                rec.season_id = False
                rec.credit_per_unit = 0.0
                rec.quota_per_unit = 0.0
            seasons_info = rec.crop_id.season_ids
            seasons = [x.season_id for x in seasons_info]
            seasons = [x.id for x in filter(lambda s: s.status == 'valid', seasons)]
            return {'domain': {'season_id': [('id', 'in', seasons)]}}

    @api.onchange('season_id')
    def _onchange_season_id(self):
        for rec in self:
            if not rec.season_id:
                continue
            season_info = filter(lambda cs: cs.crop_id == rec.crop_id \
                                  and cs.season_id == rec.season_id, rec.crop_id.season_ids)
            for si in season_info:
                rec.credit_per_unit = si.credit_per_unit
                rec.quota_per_unit = si.quota_per_unit
                rec.area = rec.partner_id._get_total_area()
                rec.season_crop_info_id = si.id
                break

    @api.depends('credit_per_unit', 'quota_per_unit', 'area')
    def _compute_amounts(self):
        amount_total = 0
        for rec in self:
            line_amount = (rec.credit_per_unit * rec.area) + (rec.quota_per_unit * rec.area)
            rec.credit_amount = line_amount
            amount_total += line_amount

        return amount_total
            
class CreditRequestReferences(models.Model):
    _name = 'farmerscredit.credit.request.references'
    _description = "Credit Request References"
    _rec_names_search = ['name', 'request_id.name']
    _order = 'request_id, id'
    _check_company_auto = True

    request_id = fields.Many2one(
        comodel_name='farmerscredit.credit.request',
        string="Request Reference",
        required=True, ondelete='cascade', index=True, copy=False)

    name = fields.Char(
        string="Reference's Name",
        required=True)

    telephone = fields.Char(
        string="Telephone",
        help="Reference's Telephone"
    )

    relationship = fields.Char(
        string="Relationship",
        help="Reference's Relationship"
    )
    
    is_personal = fields.Boolean(
        string="Personal",
        help="Indicates if this Reference is Personal (marked) or Commercial (unmarked)",
    )


class CreditRequestGuarantees(models.Model):
    _name = 'farmerscredit.credit.request.guarantees'
    _description = "Credit Request Guarantees"
    _order = 'request_id, id'
    _check_company_auto = True

    request_id = fields.Many2one(
        comodel_name='farmerscredit.credit.request',
        string="Request Reference",
        required=True, ondelete='cascade', index=True, copy=False)

    partner_id = fields.Many2one(
        related='request_id.partner_id',
        string="Applicant",
        store=True, index=True, precompute=True)
    
    # guarantee_id = fields.Many2one(
    #     comodel_name='farmerscredit.partner.guarantees',
    #     string="Request Guarantee",
    #     compute="_get_guarantee_domain",
    #     #required=True, ondelete='restrict', index=True, copy=False,
    #     #domain="_get_guarantee_domain",
    # )

    estimated_value = fields.Float(
        string="Estimated Value",
        help="Estimated value for this guarantee",
        #related='guarantee_id.estimated_value',
    )

    owner = fields.Char(
        string="Owner",
        help="Guarantee's Owner's name",
        #related='guarantee_id.owner',
    )

    @api.depends('guarantee_id')
    def _get_guarantee_domain(self):
        ids = self.partner_id.guarantee_ids.ids
        return [('id', 'in', ids)]


class CreditRequestMinistering(models.Model):
    _name = 'farmerscredit.credit.request.ministering'
    _description = 'Ministering for the Credit Request'
    _order = 'date_ministering, id'

    request_id = fields.Many2one(
        "farmerscredit.credit.request",
        string="Credit Request",
        help="General Info for Season/Crop",
    )

    credit_granted = fields.Float(
        string="Amount",
        help="Ministering Amount granted",
        digits=(10,2)
    )

    date_ministering = fields.Date(
        string="Date",
        help="Date for this ministering",
    )

    partner_id = fields.Many2one(
        'res.partner',
        related='request_id.partner_id'
    )

    def get_ministering_name(self):
        
        name = "Ministracion_" + \
                self.request_id.name.replace(' ','') + "_" + \
                datetime.strftime(self.date_ministering, "%Y_%m_%d")

        return name

    #=== REPORTS FUNCTIONS ===#
    def ministering_printing(self):

        locale.setlocale(locale.LC_ALL, 'es_ES')
        request = self.request_id
        for line in request.credit_request_line:
            date_due = line.season_id.date_end
            break

        amount_text ="${:,.2f}".format(self.credit_granted) 
        amount_principal = int(self.credit_granted)
        amount_fractional = amount_text.split(".")[1]
        company = self.request_id.company_id
        suscriber = self.partner_id
        endorse = self.request_id.partner_endorsement_id
        record_fields = {
            'company_name': company.name,
            'company_address_street_name': company.street,
            'company_address_number':company.street,
            'company_address_neighborhood': (company.street2 or ''),
            'company_address_zip_code': company.zip,
            'company_address_municipality': company.city,
            'company_address_state': company.state_id.name,
            'company_address_country': company.country_id.name,
            'season_end_dia': datetime.strftime(date_due, "%d"),
            'season_end_date_month': datetime.strftime(date_due, "%B").upper(),
            'season_end_date_year': datetime.strftime(date_due, "%Y"),
            'credit_iou_dia': datetime.strftime(self.date_ministering, "%d"),
            'credit_iou_date_month': datetime.strftime(self.date_ministering, "%B").upper(),
            'credit_iou_date_year': datetime.strftime(self.date_ministering, "%Y"),
            'credit_iou_amount_numbers': amount_text,
            'credit_iou_amount_written': company.currency_id.amount_to_text(amount_principal).upper() + \
                                           f" {amount_fractional}/100 M.N." ,
            'credit_iou_municipality': company.city,
            'credit_iou_state': company.state_id.name,
            'credit_interest_rate': "{:.2f}%".format(self.request_id.interest_rate * 100),
            'credit_arrears': self.request_id.arrears,
            'credit_arrears_written': 'DOS PUNTO CINCO',
            'partner_iou_subscriber_name': suscriber.name,
            'partner_iou_subscriber_address_street_name': suscriber.street,
            'partner_iou_subscriber_address_number':suscriber.street,
            'partner_iou_subscriber_address_neighborhood': (suscriber.street2 or ''),
            'partner_iou_subscriber_address_zip_code': suscriber.zip,
            'partner_iou_subscriber_address_municipality': suscriber.city,
            'partner_iou_subscriber_address_state': suscriber.state_id.name,
            'partner_iou_subscriber_representative': suscriber.name,
            'partner_iou_endorsement_name': endorse.name,
            'partner_iou_endorsement_address_street_name': endorse.street,
            'partner_iou_endorsement_address_number': endorse.street,
            'partner_iou_endorsement_address_neighborhood': endorse.street2 or '',
            'partner_iou_endorsement_address_zip_code': endorse.zip,
            'partner_iou_endorsement_address_municipality': endorse.city,
            'partner_iou_endorsement_address_state': endorse.state_id.name,
            'partner_iou_endorsement_representative': endorse.name,
        }

        return record_fields
    

class CreditRequestStatement(models.Model):
    _name = 'farmerscredit.credit.request.statement'
    _description = 'Statement for the Credit Request'
    _order = 'date, id'

    request_id = fields.Many2one(
        "farmerscredit.credit.request",
        string="Credit Request",
        help="General Info for Season/Crop",
    )

    move_id = fields.Many2one(
        "account.move",
        string="Move",
        help="Registered Account Move",
    )

    credit = fields.Float(
        string="Credits",
        help=" Amount paid",
        digits=(10,2)
    )

    debit = fields.Float(
        string="Debit",
        help="Credit Amount used from the Credit Request",
        digits=(10,2)
    )

    interest = fields.Float(
        string="Interest",
        help="Calculated Interest",
        digits=(10,2)
    )

    balance = fields.Float(
        string="Balance",
        help="Balance",
        digits=(10,2)
    ) 

    date = fields.Date(
        string="Date",
        help="Date for this movement",
    )

    days = fields.Integer(
        string="Days",
        help="Days for calculating interest"
    )

    ref = fields.Char(
        string="Reference",
        help="Reference for this move"
    )