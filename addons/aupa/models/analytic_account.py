# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AupaLots(models.Model):
    _inherit = ['account.analytic.account']

    is_a_lot = fields.Boolean(string="Is a Lot?", help="It is a Lot?")
    lot_size = fields.Float(string="Area Size", help="Area size of the Lot (Has)")
    lot_section = fields.Integer(string="Section", help="Lot Section")


# class AupaCrops(models.Model):
#     _inherit = 'account.analytic.tag'
#
#     is_a_crop = fields.Boolean(string="Is a Crop?", help="It is a Crop?")
#     product_ids = fields.One2many("aupa.crop.services", "analytic_tag_id")


# class AupaCropServices(models.Model):
#
#     _name = 'aupa.crop.services'
#     _description = 'Services included in the Crop'
#
#     product_id = fields.Many2one("product.product", string="Product to include", required=True)
#     product_price = fields.Float(string="Product's Price", related='product_id.list_price')
#     sale_uom = fields.Many2one("uom.uom", string="Unit of Measure")
#     analytic_tag_id = fields.Many2one("account.analytic.tag")

# class aupa(models.Model):
#     _name = 'aupa.aupa'
#     _description = 'aupa.aupa'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100
