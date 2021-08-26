# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import date

class SaleOrder(models.Model):
    _inherit = ['sale.order']


    invoice_payment_state = fields.Selection(selection=[
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid'),
        ('partial', 'Partially Paid'),
        ('reversed', 'Reversed'),
        ('invoicing_legacy', 'Invoicing App Legacy')],
        string="Payment Status", store=False, readonly=True, copy=False,
        compute='_get_invoice_payment_state')

    delivered_status = fields.Selection(
        selection=[('fd', 'Delivered'),
                    ('pd', 'Partially Delivered'),
                    ('nd', 'Not Delivered'),
                    ('no', 'Only Services')
                ], string='Delivered Status', 
                help='Show if the Sales Order has been delivered',
                compute='_get_delivered_status')

    is_courtesy = fields.Boolean(default=False, string="Is courtesy?", help="Toggle if this sale is a courtesy")
    
    l10n_mx_edi_payment_method_id = fields.Many2one('l10n_mx_edi.payment.method',
        string="Payment Way",
        help="Indicates the way the invoice was/will be paid, where the options could be: "
             "Cash, Nominal Check, Credit Card, etc. Leave empty if unkown and the XML will show 'Unidentified'.",
        default=lambda self: self.env.ref('l10n_mx_edi.payment_method_otros', raise_if_not_found=False))

    product_uom_changed = fields.Boolean(compute='_get_delivered_status', store=False)

    @api.depends('invoice_payment_state')
    def _get_invoice_payment_state(self):
        for rec in self:
            payment_state = ''
            for inv in rec.invoice_ids:
                if inv.state != 'posted':
                    continue
                payment_state = inv.payment_state
                break
            rec.invoice_payment_state = payment_state
            break

    @api.depends('delivered_status', 'product_uom_changed')
    def _get_delivered_status(self):

        for rec in self:
            status = 'nd'
            delivered = 0
            demand = 0 
            uom_changed = False
            for line in rec.order_line:
                if line.product_id.type == 'product':
                    delivered += line.qty_delivered
                    demand += line.product_uom_qty
                    if line.product_uom != line.product_id.uom_id \
                            and not uom_changed:
                        uom_changed = True
            if delivered == demand:
                status = 'fd'
            elif delivered > 0 and delivered != demand:
                status = 'pd'
            elif delivered == 0 and demand == 0:
                status = 'no' 

            rec.delivered_status = status
            rec.product_uom_changed = uom_changed
 
    #@api.multi()
    def _cancel_unconfirmed_so(self):

        today = date.today()
        domain = [('state', 'in', ['draft', 'sent'])]
        for so in self.search(domain):
            delta = today - so.create_date
            if delta.days > 6:
                so.action_cancel()



# class SaleOrderLine(models.Model):
#     _inherit = ['sale.order.line']
    
#     @api.onchange('product_uom')
#     def product_uom_change(self):
#         super(SaleOrderLine, self).product_uom_change()
#         self.order_id.product_uom_changed = True


