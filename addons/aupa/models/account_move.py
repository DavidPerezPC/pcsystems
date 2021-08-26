# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = ['account.move']

    lot_id   = fields.Many2one(
        'account.analytic.account', 
        domain="[('is_a_lot', '=', True)]",
        string="Lot to paid", 
        help="Select the Lot that will be paid")
    
    crop_id = fields.Many2one(
        'product.product',
        domain="[('pack_ok', '=', True)]",
        string="Crop to Paid", 
        help="Select the Crop that will be Paid")

    season_ids = fields.Many2many(
        'account.analytic.tag',
        string="Season and Crop Paid",   
        help="Select Season and Crop to Paid")

    
    season_name = fields.Char(
        string="Seson Paid",
        help="Season Paid in this invoice",
        store=False,
        compute="_get_season_paid")

    @api.depends('season_name')
    def _get_season_paid(self):
        for rec in self:
            season_name  = ''
            for season in rec.season_ids:
                if season.name != self.crop_id.name:
                    season_name = season.name
                    break
            rec.season_name = season_name


    # @api.onchange("crop_id")
    # def onchange_crop_id(self):
    #     if self.crop_id.pack_ok:
    #         self.mapped('invoice_line_ids').unlink()
    #         analytic_ids = [self.season_id]
    #         aml = self.env['account.move.line']
    #         for product in self.crop_id.pack_line_ids: 
    #             inv_line = {
    #                 'move_id': self.id.origin,
    #                 'product_id': product.product_id.id, 
    #                 'analytic_account_id': self.lot_id.id, 
    #                 'analytic_tag_ids': [(6, 0, analytic_ids)], 
    #                 'quantity': self.lot_id.lot_size,
    #                 'price_unit': product.product_id.lst_price,
    #               }
    #             aml.with_context(check_move_validity=False).create(inv_line)
                
    #         return



    