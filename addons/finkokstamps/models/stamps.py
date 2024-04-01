# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class ResPartner(models.Model):
    _inherit = 'res.partner'

    vat_stamps_id = fields.One2many(
        'finkokstamps.vats',
        'partner_id',
        string='Finkok',
        help="Finkok related VAT"
    )
    
class VATStamps(models.Model):
    _name = 'finkokstamps.vats'
    _description = 'VATS using Finkok service for stamping'

    stamps_ids = fields.One2many(
        'finkokstamps.stamps', 
        'vat_id', 
        string="Stamps",
        help="Stamps issued/canceled for this VAT"
    )

    name = fields.Char(
        string="Note",
        help="Notes/Comments about this VAT"
    )

    vat = fields.Char(
        string="VAT",
        help="VAT whom used these stamps",
        index=True
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        help="Customer that is related to the VAT assigned"
    )

    active = fields.Boolean(
        string="Active",
        help="Indicates if this VAT is allowed for using stamps"
    )
    #category_id = fields.Many2many(related='parter_id.category_id')
    
    def _get_id(self, vat):
        id = 0
        curvat = self.search([('vat', '=', vat)])
        if curvat:
            curvat = curvat[0]
            id = curvat.id
        else:
            data = {
                'vat': vat,
                'name': vat,
                'active': True,
            }
            curvat = self.env['res.partner'].search([('vat', '=', vat)])
            if curvat:
                curvat = curvat[0]
                data.update( {'name': curvat.name,
                              'partner_id': curvat.id} 
                              )
            id = self.create(data).id
            
        return id
    
class Stamps(models.Model):
    _name = 'finkokstamps.stamps'
    _description = 'Stamps used by Customers'

    vat_id = fields.Many2one(
        'finkokstamps.vats',
        string='VAT',
        help='VAT that used this stamps' 
    )

    name = fields.Char()

    stamps = fields.Integer(
        string="Stamps",
        help="Stamps issued"

    )
    canceled = fields.Integer(
        string="Canceled",
        help="Canceled Stamps"
    )

    date = fields.Date(
        string="From",
        help="Start date for the period of this consumption"
    )

    valid = fields.Boolean(
        string="Valid",
        help="Indicates that this consumptions has been validated"
    )
