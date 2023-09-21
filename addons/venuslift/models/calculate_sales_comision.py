# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    x_payment_info = fields.Char(
        string="Pago",
        help="ID del último pago",
        compute="_compute_payment_info",
        readonly=True, store=False,
    )

    def _compute_payment_info(self):

        for rec in self:
            idmax = 0
            vals = rec.invoice_payments_widget['content'] #_get_reconciled_info_JSON_values()
            for val in vals:
                idmax = max(idmax, val['account_payment_id'])
            rec['x_payment_info'] = idmax


class AccountPayment(models.Model):
    _inherit = "account.payment"

    x_comercial = fields.Many2one(
        comodel_name='res.users', 
        string='Comercial',
        help="Comercial (vendedor) asignado al cliente",
        related='partner_id.user_id',
        readonly=True,
    )
    x_comision = fields.Monetary(
        string="Comisión",
        help="Comisión calculada por este pago",
        compute="_compute_comision_payment",
        readonly=True
        )
    
    def _compute_comision_payment(self):

        for pay in self:
            if pay.state != 'posted' or pay.partner_type != 'customer':
                pay[('x_comision')] = 0.0
                continue
            comision = 0            
            rinvids = pay.reconciled_invoice_ids
            for inv in rinvids:
                amount_comision_base = 0  #base de comision
                amount_fletes = 0 #monto de fletes
                idmax = inv.x_payment_info.strip()
                if inv.payment_state == 'paid' and str(pay.id).strip() == inv.x_payment_info:
                    amount_invoiced = inv.amount_untaxed
                    #calcula fletes, si los hay
                    inv_fletes = inv.invoice_line_ids.filtered(lambda r: r.product_id.categ_id.id == 4)
                    for flete in inv_fletes:
                        amount_fletes += flete.price_subtotal
                    amount_comision_base += amount_invoiced - amount_fletes 
                    sorders = self.env['sale.order'].search([('name', '=', inv.invoice_origin)])
                    for so in sorders:
                        comision += so.pricelist_id.x_studio_comision_to_pay * amount_comision_base 
            pay['x_comision'] = comision

