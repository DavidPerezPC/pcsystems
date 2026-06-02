# -*- coding: utf-8 -*-
import logging
from datetime import timedelta
from odoo import models, api

_logger = logging.getLogger(__name__)


class AvcoKardex(models.AbstractModel):
    _name = 'avco.kardex'
    _description = 'Generador de Kardex AVCO'

    @api.model
    def _compute_initial_state(self, product, company, date_from, history_from=None):
        """
        Calcula qty y avco iniciales procesando moves en [history_from, date_from).
        Si history_from es None procesa toda la historia anterior a date_from.
        Retorna (qty, avco, moves_found).
        """
        replay = self.env['avco.replay']
        domain = [
            ('product_id', '=', product.id),
            ('state', '=', 'done'),
            ('date', '<', date_from),
            ('company_id', '=', company.id),
        ]
        if history_from:
            domain.append(('date', '>=', history_from))

        prev_moves = self.env['stock.move'].search(domain, order='date asc, id asc')

        _logger.info(
            "AvcoKardex [%s] company=%s date_from=%s history_from=%s → %d moves previos",
            product.display_name, company.name, date_from, history_from, len(prev_moves),
        )

        qty = 0.0
        avco = 0.0
        for m in prev_moves:
            src_int = m.location_id.usage == 'internal'
            dst_int = m.location_dest_id.usage == 'internal'
            if dst_int and not src_int:
                unit_cost, _ = replay._get_incoming_unit_cost(m, 0.0, avco, company)
                qty_in = m.quantity
                if qty + qty_in > 0:
                    avco = (qty * avco + qty_in * unit_cost) / (qty + qty_in)
                qty += qty_in
            elif src_int and not dst_int:
                qty -= m.quantity

        _logger.info(
            "AvcoKardex [%s] qty_inicial=%.4f avco_inicial=%.6f",
            product.display_name, qty, avco,
        )
        return qty, avco, len(prev_moves)

    @api.model
    def generate_kardex(self, product, company, date_from, date_to,
                        history_from=None):
        replay = self.env['avco.replay']

        qty, avco, prev_count = self._compute_initial_state(
            product, company, date_from, history_from
        )

        if prev_count:
            inicio_ref = f'{prev_count} mov. previos'
        else:
            inicio_ref = f'Sin movimientos antes de {date_from}'
            if history_from:
                inicio_ref += f' (desde {history_from})'

        rows = [{
            'producto': product.display_name,
            'fecha': str(date_from),
            'tipo': 'INICIO',
            'move_id': '',
            'ref': inicio_ref,
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
