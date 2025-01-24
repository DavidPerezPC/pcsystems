# -*- coding: utf-8 -*-

from odoo import models, fields, tools, api, _
from odoo.tools import get_lang
from datetime import datetime, timedelta
from lxml import etree


class StockPicking(models.Model):
    _inherit = ['stock.picking']

    def get_data_toprint(self):

        picking = self.picking_type_id
        if picking.code != 'outgoing':
            notification = {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Impresión de Salida'),
                    'type': 'warning',
                    'message': f"El movimiento no es de entrega, no existe formato para este movimiento",
                    'sticky': True,
                        }
                }
            return False
        partner_id = self.partner_id
        warehouse_name = picking.warehouse_id.name
        carrier_name = self.carrier_id.name
        tracking_ref = self.carrier_tracking_ref
        responsible_name = self.user_id.name
        sale_order = self.group_id.name
        notes = ''
        if self.note:
            html_notes = self.note
            plain_text = etree.HTML(html_notes).xpath('//text()')
            notes = ''.join(plain_text)
 

        line_ids = self._get_picking_lines() 

        picking_vals = {
            'number': self.name,
            'partner_name': partner_id.name,
            'warehouse_name': warehouse_name or '',
            'carrier_name': carrier_name or '',
            'carrier_tracking_ref': tracking_ref or '',
            'responsible_name': responsible_name or '',
            'sale_order': sale_order,
            'date_done': self.date_done.strftime("%d  %m  %Y"),
            'notes': notes or '',
            'line_ids': line_ids,
        }

        return picking_vals
    
    def _get_picking_lines(self):

        line_ids = []
        for line in self.move_line_ids:
            line_uom = line.product_uom_id.unspsc_code_id
            product_name = line.display_name
            data = {
                'clave': line.product_id.default_code,
                'product_id': line.product_id.unspsc_code_id.code,
                'uom': f"{line_uom.code} {line_uom.name}",
                'product_name': product_name,
                'qty': line.qty_done,
            }
            line_ids.append(data)
        
        return line_ids