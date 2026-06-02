# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import models, api


class AvcoKardex(models.AbstractModel):
    _name = 'avco.kardex'
    _description = 'Generador de Kardex AVCO'

    @api.model
    def generate_kardex(self, product, company, date_from, date_to):
        """
        Genera las filas del kardex para un producto en el rango [date_from, date_to].

        Delega el cálculo del estado inicial y los costos unitarios a avco.replay
        para mantener la lógica de AVCO en un solo lugar.

        Retorna (rows, totals):
          rows   — lista de dicts listos para volcar al Excel
          totals — dict con resumen del producto al cierre del período
        """
        replay = self.env['avco.replay']

        qty, avco = replay._get_initial_state(product, company, date_from, 0.0)

        rows = [{
            'producto': product.display_name,
            'fecha': str(date_from),
            'tipo': 'INICIO',
            'move_id': '',
            'ref': '',
            'existencia_anterior': 0.0,
            'entrada': 0.0,
            'salida': 0.0,
            'costo_movimiento': avco,
            'nuevo_costo': avco,
            'existencia': qty,
            'valor_inventario': qty * avco,
        }]

        domain = [
            ('product_id', '=', product.id),
            ('state', '=', 'done'),
            ('date', '>=', date_from),
            ('company_id', '=', company.id),
        ]
        if date_to:
            # < día siguiente para incluir todos los movimientos del date_to
            domain.append(('date', '<', date_to + timedelta(days=1)))

        moves = self.env['stock.move'].search(domain, order='date asc, id asc')

        total_in = 0.0
        total_out = 0.0

        for m in moves:
            src_int = m.location_id.usage == 'internal'
            dst_int = m.location_dest_id.usage == 'internal'

            if dst_int and not src_int:
                qty_before = qty
                unit_cost, _ = replay._get_incoming_unit_cost(m, 0.0, avco, company)
                qty_in = m.quantity
                if qty + qty_in > 0:
                    avco = (qty * avco + qty_in * unit_cost) / (qty + qty_in)
                qty += qty_in
                total_in += qty_in
                rows.append({
                    'producto': product.display_name,
                    'fecha': str(m.date),
                    'tipo': 'IN',
                    'move_id': m.id,
                    'ref': replay._get_move_ref(m),
                    'existencia_anterior': qty_before,
                    'entrada': qty_in,
                    'salida': 0.0,
                    'costo_movimiento': unit_cost,
                    'nuevo_costo': avco,
                    'existencia': qty,
                    'valor_inventario': qty * avco,
                })

            elif src_int and not dst_int:
                qty_before = qty
                qty_out = m.quantity
                qty -= qty_out
                total_out += qty_out
                rows.append({
                    'producto': product.display_name,
                    'fecha': str(m.date),
                    'tipo': 'OUT',
                    'move_id': m.id,
                    'ref': replay._get_move_ref(m),
                    'existencia_anterior': qty_before,
                    'entrada': 0.0,
                    'salida': qty_out,
                    'costo_movimiento': avco,
                    'nuevo_costo': avco,
                    'existencia': qty,
                    'valor_inventario': qty * avco,
                })

            else:
                rows.append({
                    'producto': product.display_name,
                    'fecha': str(m.date),
                    'tipo': 'INT',
                    'move_id': m.id,
                    'ref': replay._get_move_ref(m),
                    'existencia_anterior': qty,
                    'entrada': 0.0,
                    'salida': 0.0,
                    'costo_movimiento': 0.0,
                    'nuevo_costo': avco,
                    'existencia': qty,
                    'valor_inventario': qty * avco,
                })

        totals = {
            'producto': product.display_name,
            'total_in': total_in,
            'total_out': total_out,
            'qty_final': qty,
            'avco_final': avco,
            'valor_final': qty * avco,
        }
        return rows, totals
