# -*- coding: utf-8 -*-

from odoo import models, fields, tools, api, _
from odoo.tools import get_lang
from datetime import datetime, timedelta


class PurchaseOrder(models.Model):
    _inherit = ['purchase.order']

    @api.model
    def default_get(self, fields_list):
        res = super(PurchaseOrder, self).default_get(fields_list)
        if 'picking_type_id' in res and res['picking_type_id']:
            deliveryaddress_id = self.env['stock.picking.type'].browse(res['picking_type_id']).warehouse_id.partner_id.id
            res.update({'delivery_address': deliveryaddress_id})
        return res
    
    @api.onchange("picking_type_id")
    def _get_delivery_address(self):
        self.delivery_address = self.picking_type_id.warehouse_id.partner_id.id

    delivery_address = fields.Many2one(
        comodel_name='res.partner',
        string="Delivery Address",
        help="Addres where the products will be delivered",
        domain=[('type', '=', 'delivery'), ('company_type', '=', 'person')], 
    )

    def get_data_toprint(self):

        partner_id = self.partner_id
        street =  f"{partner_id.street or ''} {partner_id.street2 or ''} {partner_id.zip or ''}"
        city_state  = f"{partner_id.city or ''} {partner_id.city_id.name or ''} {partner_id.state_id.name or ''} {partner_id.country_id.name or ''}"
        ship_to = self.delivery_address
        ship_to_name = ship_to.name
        ship_to_street =  f"{partner_id.street or ''} {partner_id.street2 or ''} {partner_id.zip or ''}"
        ship_to_city_state  = f"{partner_id.city or ''} {partner_id.city_id.name or ''} {partner_id.state_id.name or ''} {partner_id.country_id.name or ''}"
        tax_totals = self.tax_totals
        amt_total = f"{tax_totals['total_amount_currency']}"
        amt_entero = int(self.amount_total)
        amt_decimal = round(float("0."+amt_total.split(".")[1]),2)
        amt_decimal = (str(amt_decimal).split(".")[1] + "0000")[:2]

        amount_ieps = 0
        amount_iva = 0
        for tax in tax_totals['subtotals'][0]['tax_groups']:
            group_name = tax['group_name']
            group_amount = tax['display_base_amount_currency']
            if group_name[:4] == 'IEPS':
                amount_ieps += group_amount
            elif group_name[:3] == 'IVA':
                amount_iva += group_amount
        dp = f"{self.currency_id.decimal_places}f"
        expr = '"${:,.' + dp + '}".format(amount_ieps)'
        amt_ieps = eval(expr)
        expr = '"${:,.' + dp + '}".format(amount_iva)'
        amt_iva = eval(expr)

        line_ids = self._get_po_lines() 

        po_vals = {
            'partner_name': partner_id.name,
            'street': street,
            'city_state': city_state,
            'ship_to_name': ship_to_name,
            'ship_to_street': ship_to_street,
            'ship_to_city_state': ship_to_city_state,
            'number': self.name,
            'date_order': self.date_approve.strftime("%d  %m  %Y"),
            'date_due': self.date_planned.strftime("%d/%m/%Y"),
            'approver': self.user_id.name,
            'line_ids': line_ids,
            'amt_untax': self.amount_untaxed,
            'amt_iva': amt_iva,
            'amt_ieps': amt_ieps,
            'amt_total': self.amount_total,
            'amt_text': f"{self.currency_id.amount_to_text(amt_entero)} {amt_decimal}/100 {self.currency_id.name}".upper(),
        }

        return po_vals
    
    def _get_po_lines(self):

        line_ids = []
        for line in self.order_line:
            line_uom = line.product_uom.unspsc_code_id
            tiva = ''
            tieps= ''
            product_ctx = {'seller_id': line.partner_id.id, 'lang': get_lang(line.env, line.partner_id.lang).code}
            try:
                product_name = line._get_product_purchase_description(line.product_id.with_context(product_ctx))
            except Exception as ex:
                product_name = line.product_id.description_purchase or line.product_id.name
                pass
            for tax in line.taxes_id:
                if tax.name[:4] == 'IEPS':
                    tieps += f"{tax.name},"
                elif tax.name[:3] == 'IVA':
                    tiva += f"{tax.name},"
            tiva = tiva[:len(tiva)-1]
            tieps = tieps[:len(tieps)-1]
            data = {
                'clave': line.product_id.default_code,
                'product_id': line.product_id.unspsc_code_id.code,
                'uom': f"{line_uom.code} {line_uom.name}",
                'product_name': product_name,
                'qty': line.product_qty,
                'price': "{:,.4f}".format(line.price_unit),
                'taxobj': '02',
                'tiva': tiva,
                'tieps': tieps,
                'subtotal': "{:,.4f}".format(line.price_subtotal)
            }
            line_ids.append(data)
        
        return line_ids