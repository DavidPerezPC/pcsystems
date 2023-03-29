# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
#from lxml import etree
from datetime import date

class Partner(models.Model):
    _inherit = ['res.partner']

    type = fields.Selection(
        [('contact', 'Contact'),
         ('invoice', _('Representative')),
         ('delivery', _('Notary')),
         ('private', _('Endorsement')),
         ('other', _('Mate')),
        ], string='Contact Type',
        default='private',
        help=_(\
             "- Contact: Use this to organize the contact details of employees of a given company (e.g. CEO, CFO, ...).\n"
             "- Representative : Legal Representative for this Partner.\n"
             "- Notary : Notary that validatet the Public Deed.\n"
             "- Endorsement: Person who supports in case the borrower presents problems during the term of the contract, ...).\n"
             "- Mate: Mate or Spouse of the borrower, ...)")
            )
    
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

    guarantee_ids = fields.One2many(
        'farmerscredit.partner.guarantees', 'partner_id', 
        string="Farmer's guarantees",
        help="Enter Farmer's guarantees")

    lot_ids = fields.One2many(
        'farmerscredit.partner.lots', 'partner_id',
        string="Farmer's lots",
        help="Enter Farmer's Lots")
    
    total_area = fields.Float(
        string="Total Area",
        help="Total area available for credit",
        compute="_get_total_area", store=True, readonly=True,
    )

    #INFORMACIÓN PARA NOTARIOS (type=DELIVERY) y REPRESENTANTES (type=INVOICE)
    public_deed_num = fields.Char(
        string="Public Deed#",
        help="Type the Public Deed Number"
    )

    public_deed_vol = fields.Char(
        string = "Volume",
        help = "Volume# where the Public Deed was registered" 
    )

    public_deed_date = fields.Date(
        string="Date",
        help="Date that this Public Deed was registered"
    )

    public_deed_notary_num = fields.Char(
        string="Notary#",
        help="Notary authorization number that registered this Public Deed"
    )

    public_deed_notary_municipality = fields.Char(
        string="Municipality",
        help="Municipality that this Notary was authorized"
    )

    public_deed_notary_state  = fields.Char(
        string="State",
        help="State that this Notary was authorized"
    )

    business_folio = fields.Char(
        string="Folio",
        help="Folio assigned for Public Deed"
    )

    business_folio_date = fields.Date(
        string="Date",
        help="Issued Date for this Folio"
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

    @api.depends('lot_ids')    
    def _get_total_area(self):
        area = 0
        for partner in self:
            for lot in partner.lot_ids:
                area += lot.area
            partner.total_area = area

        return area
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
    
    name = fields.Char(
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

    # def name_get(self):
    #     res = []
    #     for rec in self:
    #         res.append((rec.id, rec.description))
    #     return res
    
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

    area = fields.Float(
        string="Area",
        help="Enter lot's area",
        digits=(10,2))

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