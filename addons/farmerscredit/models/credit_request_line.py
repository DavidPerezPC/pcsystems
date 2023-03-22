# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from datetime import timedelta

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
        string="Season/Crop Info",
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
