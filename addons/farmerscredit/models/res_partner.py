# -*- coding: utf-8 -*-

from odoo import models, fields, api
from lxml import etree

class Partner(models.Model):
    _inherit = ['res.partner']

    curp = fields.Char(
        string="CURP", 
        help="Enter the Unique Identification Population Key assigned by Goverment", 
        size=18)

    is_farmer = fields.Boolean(
        string='Is Farmer?',  
        help="Toggle to indicate if is a Farmer or not",
        default=False)
 
    ine = fields.Char(
        string="INE", 
        help="Enter the INE number issued by Goverment", 
        size=14)

    birth_certificate = fields.Char(
        string="Brith Certificate",
        help="Enter the Birht Certifcate number",
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

    guarantee_ids = fields.One2many(
        'farmerscredit.partner.guarantees', 'partner_id', 
        string="Farmer's guarantees",
        help="Enter Farmer's guarantees")

    lot_ids = fields.One2many(
        'farmerscredit.partner.lots', 'partner_id',
        string="Farmer's lots",
        help="Enter Farmer's Lots")

class PartnerGuarantees(models.Model):
    _name = 'farmerscredit.partner.guarantees'
    _description = 'Guarantees given by Farmers'

    partner_id = fields.Many2one(
        'res.partner',
        string='Farmer',
        help="Farmer owner of these guarantees")

    type = fields.Selection(
        string="Guarantee Type",
        help="Select the guarantee type",
        selection=[('pledge', 'Pledge'),
                    ('mortgage', 'Mortgage'),
                    ('beneficial', 'Beneficial Owner'),
                ],
        default='pledge')
    
    description = fields.Char(
        string="Description",
        help="Property/Good description or features")

    doc_number = fields.Char(
        string="Document #",
        help="Enter the Document Number for this guarantee")

    issued_date = fields.Date(
        string="Issued date",
        help="Enter issued date for this document")

    owner = fields.Char(
        string="Owner",
        help="Enter Guarantee's Owner's name")
    
    estimated_value = fields.Float(
        string="Estimated Value",
        help="Enter the estimated value for this guarantee")

    estimated_date = fields.Date(
        string="Estimate's Date",
        help="Enter the Estimation's date")

    proficient = fields.Char(
        string="Proficient",
        help="Enter the proficient's name")

    #aplica para pledge y beneficial
    supplier = fields.Char(
        string="Supplier",
        help="Enter the supplier for this guarantee")

    #aplica para mortgage
    notary = fields.Char(
        string="Notary",
        help="Enter the notary that issued this guarantee")
    
    inscription = fields.Char(
        string="Inscription",
        help="Enter the inscription for this guarantee")

    inscription_folio = fields.Char(
        string="Folio",
        help="Enter the Inscriptio's Folio for this guarantee")

    book = fields.Char(
        string="Book",
        help="Enter the Book where this guarantte was registered")

    section = fields.Char(
        string="Section",
        help="Enter the book's section for this guarantee")    


class PartnerLots(models.Model):
    _name = 'farmerscredit.partner.lots'
    _description = "Lots of the Farmers"

    partner_id = fields.Many2one(
        'res.partner',
        string='Farmer',
        help="Farmer's lots owner")

    type = fields.Selection(
        string="Owner Type",
        help="Select the owner type for this lot",
        selection=[('own', 'Owner'),
                    ('leased', 'Leased'),
                ],
        default='own')
    
    ownership_type = fields.Selection(
        string="Ownership Type",
        help="Select the ownership type for this lot",
        selection=[('parcel', 'Parcel Certificate'),
                    ('public', 'Public Document'),
                    ('other', 'Other'),
                ],
        default='parcel')
  
    doc_number = fields.Char(
        string="Document #",
        help="Enter the Document Number for this lot")


    location = fields.Char(
        string="Location",
        help="Enter location for this lot")

    area = fields.Char(
        string="Area",
        help="Enter lot's area")

    owner = fields.Char(
        string="Owner",
        help="Enter lot's Owner's name")

    initial_date = fields.Date(
        string="Initial Date",
        help="Enter initial date for this contract")

    end_date = fields.Date(
        string="End Date",
        help="Enter end date for this contract")

    #aplica para parcel y public, la etiqueta es Agrarian or Document Register
    register = fields.Char(
        string="Agrarian/Public Reg",
        help="Enter the Agrarian (if is Parcel) or Public register (if is Public)")

    #aplica para parcel
    parcel_number = fields.Char(
        string="Parcel number",
        help="Enter the parcer number for this lot")


    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        result = super(PartnerLots, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if view_type == 'form':
            doc = etree.XML(result['arch'])
            reg_reference = doc.xpath("//field[@name='register']")
            if reg_reference:
                if self.ownership_type == 'parcel':
                    reg_reference[0].set("string", "Agrarian Reg")
                elif self.ownership_type == 'public':
                    reg_reference[0].set("string", "Public Reg")
                result['arch'] = etree.tostring(doc, encoding='unicode')
        
        return result