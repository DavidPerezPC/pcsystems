# -*- coding: utf-8 -*-

from email.policy import default
from urllib.parse import quote_from_bytes
from odoo import models, fields, api
import datetime as dt

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

    is_courtesy = fields.Boolean(default=False, 
        string="Is courtesy?", 
        help="Toggle if this sale is a courtesy")
    ready_to_deliver = fields.Boolean(default=False, 
            string="Ready to Deliver", 
            help="Indicates that Sale Order can be delivered")        
    l10n_mx_edi_payment_method_id = fields.Many2one('l10n_mx_edi.payment.method',
        string="Payment Way",
        help="Indicates the way the invoice was/will be paid, where the options could be: "
             "Cash, Nominal Check, Credit Card, etc. Leave empty if unkown and the XML will show 'Unidentified'.",
        default=lambda self: self.env.ref('l10n_mx_edi.payment_method_otros', raise_if_not_found=False))

    product_uom_changed = fields.Boolean(compute='_get_delivered_status', store=False)
    has_negative_stock = fields.Boolean(compute='_get_delivered_status',
            string="Negative Stock", 
            help="Indicates if a line item has no stock available")

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

    def action_confirm(self):
        self._get_delivered_status()
        if self.has_negative_stock:
            return 
        return super(SaleOrder, self).action_confirm()

    @api.depends('delivered_status', 'product_uom_changed', 'has_negative_stock')
    def _get_delivered_status(self):
        sq_obj = self.env['stock.quant']
        for rec in self:
            status = 'nd'
            delivered = 0
            demand = 0 
            uom_changed = False
            has_negative_stock = False
            location_id = rec.warehouse_id.lot_stock_id
            for line in rec.order_line:
                if line.product_id.type == 'product':
                    delivered += line.qty_delivered
                    demand += line.product_uom_qty
                    if line.product_uom != line.product_id.uom_id \
                            and not uom_changed:
                        uom_changed = True   
                    
                    if rec.state in ['draft', 'sent'] and \
                             not has_negative_stock:
                        qty_available = sq_obj._get_available_quantity(line.product_id, location_id)          
                        has_negative_stock = (qty_available < line.product_uom_qty)
                
            if delivered == demand:
                status = 'fd'
            elif delivered > 0 and delivered != demand:
                status = 'pd'
            elif delivered == 0 and demand == 0:
                status = 'no' 

            rec.delivered_status = status
            rec.product_uom_changed = uom_changed
            rec.has_negative_stock = has_negative_stock
 
    #@api.multi()
    def _cancel_unconfirmed_so(self):

        today = dt.datetime.now()
        days = dt.timedelta(4)
        date_to = dt.datetime.strftime(today - days, '%Y-%m-%d')
        domain = [('state', 'in', ['draft', 'sent']),
                    ('create_date', '<=', date_to),
                    #('delivered_status', '=', 'nd'),
                    #('invoice_payment_state', '=', 'not_paid')
                    ]
        sos = self.search(domain)
        for so in sos:
            so.action_cancel()

# class SaleOrderLine(models.Model):
#     _inherit = ['sale.order.line']
    

#     has_negative_stock = fields.Boolean(store=True,
#             string="Negative Stock", 
#             help="Indicates if a line item has no stock available")

#     @api.onchange('product_uom', 'product_uom_qty')
#     def product_uom_change(self):
#         super(SaleOrderLine, self).product_uom_change()
#         if self.product_id and self.product_id.type == 'product':
#             sq_obj = self.env['stock.quant']
#             location_id = self.order_id.warehouse_id.lot_stock_id
#             qty_available = sq_obj._get_available_quantity(self.product_id, location_id)
#             self.write({'has_negative_stock': (qty_available < self.product_uom_qty)})
#             # if not self.order_id.has_negative_stock:
#             #     self.order_id._get_delivered_status()

