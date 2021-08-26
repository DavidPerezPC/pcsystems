# -*- coding: utf-8 -*-

from odoo import models, fields, api

class AccountMoveWizard(models.TransientModel):
    """Invoice Generation Wizard"""

    _name = "account.move.wizard"
    _description = "Wizard for Customer Invoice Creation"

    lot_id   = fields.Many2one(
        'account.analytic.account', 
        domain="[('is_a_lot', '=', True)]",
        string="Lot to paid", 
        help="Select the Lot that will be paid")

    lot_size = fields.Float(
        related="lot_id.lot_size", 
        readonly=False,
        string="Area Size", 
        help="Area size of the Lot (Has)")

    lot_section = fields.Integer(
        related="lot_id.lot_section",
        string="Section", help="Lot Section")

    crop_id = fields.Many2one(
        'product.product',
        domain="[('pack_ok', '=', True)]",
        string="Crop to Paid", 
        help="Select the Crop that will be Paid")

    season_ids = fields.Many2many(
        'account.analytic.tag',
        string="Season", 
        help="Select Season and Crop to Paid")
    
    partner_id = fields.Many2one(
        'res.partner',
         string="Customer",
        help="Select Customer to Invoice",
    )

    @api.onchange("crop_id")
    def _onchange_crop_id(self):    
        self._get_analytic_tags()
        return 

    def _get_analytic_tags(self):
        rec = self.env['account.analytic.default'].account_get(
            product_id=self.crop_id.id,
            partner_id=False,
            account_id=False,
            user_id=False,
            date=False,
            company_id=1
        )
        if rec:
            self.season_ids = rec.analytic_tag_ids

    def _create_customer_invoice(self):
        inv_lines = []
        analytic_ids = self.season_ids.ids
        for product in self.crop_id.pack_line_ids:
            inv_lines.append([0, 0, 
                {
                    'product_id': product.product_id.id,
                    'product_uom_id': product.product_id.uom_id.id, 
                    'analytic_account_id': self.lot_id.id, 
                    'quantity': self.lot_id.lot_size, 
                    'price_unit': product.product_id.lst_price,
                    'analytic_tag_ids': [(6, 0, analytic_ids)],
                }])

        invoice = self.env['account.move'].create(
            {
                'partner_id': self.partner_id.id, 
                'lot_id': self.lot_id.id,
                'crop_id': self.crop_id.id,
                'season_ids': analytic_ids,
                'move_type': 'out_invoice', 
                'invoice_line_ids': inv_lines
            })

        return invoice
    
    def create_and_view_invoice(self):
        invoices = self._create_customer_invoice()
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_out_invoice_type")
        form_view = [(self.env.ref('account.view_move_form').id, 'form')]
        action['views'] = form_view
        action['res_id'] = invoices.id
        context = {
            'default_move_type': 'out_invoice',
        }
        action['context'] = context
        return action


    # def create_and_view_invoice(self):
    #     invoices = self._create_customer_invoice()
    #     action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_out_invoice_type")
    #     if len(invoices) > 1:
    #         action['domain'] = [('id', 'in', invoices.ids)]
    #     elif len(invoices) == 1:
    #         form_view = [(self.env.ref('account.view_move_form').id, 'form')]
    #         if 'views' in action:
    #             action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
    #         else:
    #             action['views'] = form_view
    #         action['res_id'] = invoices.id
    #     else:
    #         action = {'type': 'ir.actions.act_window_close'}

    #     context = {
    #         'default_move_type': 'out_invoice',
    #     }
    #     # if len(self) == 1:
    #     #     context.update({
    #     #         'default_partner_id': self.partner_id.id,
    #     #         'default_partner_shipping_id': self.partner_shipping_id.id,
    #     #         'default_invoice_payment_term_id': self.payment_term_id.id or self.partner_id.property_payment_term_id.id or self.env['account.move'].default_get(['invoice_payment_term_id']).get('invoice_payment_term_id'),
    #     #         'default_invoice_origin': self.mapped('name'),
    #     #         'default_user_id': self.user_id.id,
    #     #     })
    #     action['context'] = context
    #     return action
