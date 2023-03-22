# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from lxml import etree
from odoo.exceptions import AccessError, UserError, ValidationError

class Seasons(models.Model):
    _name = 'farmerscredit.seasons'
    _description = "Seasons used in Credits " 

    name = fields.Char(
        string="Name", 
        help="Name of the season", 
        )

    date_start = fields.Date(
        string='Date from',  
        help="Starting date of this Season"
        )
 
    date_end = fields.Date(
        string='Date to',  
        help="Ending date of this Season"
        )
    
    status = fields.Selection(
            [('valid', 'Valid'),
             ('done', 'Done'),
             ('discharged', 'Discharged')
            ], 
            string='Status', 
            help="Status of the Season, only valid can be used with operations",
            default='valid')
    
    active = fields.Boolean(default=True)
    
    crop_ids = fields.One2many(
            'farmerscredit.season.crop.info', 
            'season_id', 
            string='Crop',
            help="Crop used in this Season",
            auto_join=True)
    
    _sql_constraints = [
        ('unique_name', "UNIQUE(name)", 'Season requires a UNIQUE name'),
    ]

    @api.constrains('crop_ids')
    def _check_line_amounts(self):
        
        errors = ""
        crops = []
        for line in self.crop_ids:
            if line.credit_per_unit < (line.ministering1_amount+line.ministering2_amount+line.ministering3_amount):
                errors += _(f'Sum of ministering must be less o equal to Credit per Ha., in Crop: {line.crop_id.name}\n')
            
            if line.crop_id.id in crops:
                errors += _(f'Crop {line.crop_id.name} is duplicated. \n')
            
            crops.append(line.crop_id.id)
        
        if errors != "":
            raise ValidationError(errors)
            return False

        return True

class Crops(models.Model):
    _name = 'farmerscredit.crops'
    _description = 'Crops where Credits are issued'

    name = fields.Char(
        string="Name", 
        help="Name of the Crop", 
        )

    months = fields.Integer(
        string="Months",
        help="Maximum number of months for this Crop (0 for no limit)",
        default=0)

    active = fields.Boolean(default=True)

    season_ids = fields.One2many(
            'farmerscredit.season.crop.info', 
            'crop_id', 
            string='Season',
            help="Season where this Crop is used",
            auto_join=True)

    _sql_constraints = [
        ('unique_name', "UNIQUE(name)", 'Crop requires a name'),
    ]

    @api.constrains('season_ids')
    def _check_line_amounts(self):
        
        errors = ""
        seasons = []
        for line in self.season_ids:
            if line.credit_per_unit < (line.ministering1_amount+line.ministering2_amount+line.ministering3_amount):
                errors += _(f'Sum of ministering must be less o equal to Credit per Ha., in Season: {line.season_id.name}\n')
            
            if line.season_id.id in seasons:
                errors += _(f'Season {line.season_id.name} is duplicated. \n')
            
            seasons.append(line.season_id.id)
        
        if errors != "":
            raise ValidationError(errors)
            return False

        return True

class SeasonCropsInfo(models.Model):
    _name = 'farmerscredit.season.crop.info'
    _description = 'Information for Seasons and Crops'

    season_id = fields.Many2one(
        "farmerscredit.seasons",
        string="Season"   
    )

    crop_id = fields.Many2one(
        "farmerscredit.crops",
        string="Crop"
    )
    
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

    ministering1_amount = fields.Float(
        string="Minist 1",
        help="Amount per Ha for First Ministering",
        digits=(10,2),
        default=0,
    )

    ministering2_amount = fields.Float(
        string="Minist 2",
        help="Amount per Ha for Second Ministering",
        digits=(10,2),
        default=0,
    )

    ministering3_amount = fields.Float(
        string="Minist 3",
        help="Amount per Ha for Third Ministering",
        digits=(10,2),
        default=0,
    )

    ministering1_date = fields.Date(
        string="Date M1",
        help="Date for First Ministering",
        default=lambda self: self._get_date(1),
    )

    ministering2_date = fields.Date(
        string="Date M2",
        help="Date for Second Ministering",
        default=lambda self: self._get_date(2),
    )

    ministering3_date = fields.Date(
        string="Date M3",
        help="Date for Third Ministering",
        default=lambda self: self._get_date(3),
    )
    
    @api.onchange("season_id")
    def _onchange_season_id(self):

        self.ministering1_date = self._get_date(1)
        self.ministering2_date = self._get_date(2)
        self.ministering3_date = self._get_date(3)

    def _get_date(self, ministering):
        ministering -= 1
        default_season_id = self._context.get('default_season_id')
        if not self.season_id.id and default_season_id:
            season = self.env['farmerscredit.seasons'].search([('id', '=', default_season_id)])[0]
            if season:
                date_start = season.date_start
                date_end = season.date_end
        elif self.season_id.id:
            date_start = self.season_id.date_start
            date_end = self.season_id.date_end
        else:
            return fields.date.today()
        months=['09', '12', '01']
        years=[date_start, date_start, date_end]
        year = years[ministering]
        default_date = year.strftime(f"%Y-{months[ministering]}-01")
        return default_date

    @api.onchange('credit_per_unit', 'ministering1_amount', 'ministering2_amount', 'ministering3_amount')
    def _onchange_amounts(self):
        self._compute_amounts()

    @api.depends('credit_per_unit', 'ministering1_amount', 'ministering2_amount', 'ministering3_amount')
    def _compute_amounts(self):

        for rec in self:
            if rec.ministering1_amount == 0:
                rec.ministering1_amount = rec.credit_per_unit
            
            if rec.ministering2_amount == 0:
                rec.ministering2_amount = rec.credit_per_unit - rec.ministering1_amount
                
            if rec.ministering3_amount == 0:
                rec.ministering3_amount = rec.credit_per_unit - rec.ministering1_amount - rec.ministering2_amount

        return True

# class SeasonCropMinistering(models.Model):
#     _name = 'farmerscredit.season.crop.ministering'
#     _description = 'Ministering for Seasons and Crops'
#     _order = 'date_ministering desc, id'

#     season_crop_id = fields.Many2one(
#         "farmerscredit.season.crop.info",
#         string="Season/Crop Info",
#         help="Genaral Info for Season/Crop",
#     )

#     credit_per_unit = fields.Float(
#         string="Credit x Ha.",
#         help="Credit Amount per Hectare for this Ministering",
#         digits=(10,2)
#     )

#     date_ministering = fields.Date(
#         string="Date",
#         help="Date for this ministering",
#     )

# class TradingCompanies(models.Model):
#     _name = 'farmerscredit.tradingcompanies'
#     _description = "Companies that fundd your Credits"

#     partner_id = fields.Many2one(
#         'res.partner',
#         string='Farmer',
#         help="Farmer's lots owner")

#     type = fields.Selection(
#         string="Owner Type",
#         help="Select the owner type for this lot",
#         selection=[('own', 'Owner'),
#                     ('leased', 'Leased'),
#                 ],
#         default='own')
    
#     ownership_type = fields.Selection(
#         string="Ownership Type",
#         help="Select the ownership type for this lot",
#         selection=[('parcel', 'Parcel Certificate'),
#                     ('public', 'Public Document'),
#                     ('other', 'Other'),
#                 ],
#         default='parcel')
  
#     doc_number = fields.Char(
#         string="Document #",
#         help="Enter the Document Number for this lot")


#     location = fields.Char(
#         string="Location",
#         help="Enter location for this lot")

#     area = fields.Char(
#         string="Area",
#         help="Enter lot's area")

#     owner = fields.Char(
#         string="Owner",
#         help="Enter lot's Owner's name")

#     initial_date = fields.Date(
#         string="Initial Date",
#         help="Enter initial date for this contract")

#     end_date = fields.Date(
#         string="End Date",
#         help="Enter end date for this contract")

#     #aplica para parcel y public, la etiqueta es Agrarian or Document Register
#     register = fields.Char(
#         string="Agrarian/Public Reg",
#         help="Enter the Agrarian (if is Parcel) or Public register (if is Public)")

#     #aplica para parcel
#     parcel_number = fields.Char(
#         string="Parcel number",
#         help="Enter the parcer number for this lot")


#     @api.model
#     def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
#         result = super(PartnerLots, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
#         if view_type == 'form':
#             doc = etree.XML(result['arch'])
#             reg_reference = doc.xpath("//field[@name='register']")
#             if reg_reference:
#                 if self.ownership_type == 'parcel':
#                     reg_reference[0].set("string", "Agrarian Reg")
#                 elif self.ownership_type == 'public':
#                     reg_reference[0].set("string", "Public Reg")
#                 result['arch'] = etree.tostring(doc, encoding='unicode')
        
#         return result