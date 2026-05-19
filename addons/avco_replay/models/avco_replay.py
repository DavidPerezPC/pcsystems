# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AvcoReplay(models.AbstractModel):
    """
    Servicio de replay de AVCO.

    Reproduce la historia de stock.move de un producto desde una fecha de corte,
    recalculando el costo promedio ponderado considerando:
      - Entradas por compra (precio del PO o factura)
      - Entradas por ajuste manual (usa costo manual proporcionado)
      - Salidas (valoradas al AVCO vigente, no modifican promedio)
      - Landed costs (costos en destino) sumados al costo unitario de entrada
      - Facturas de proveedor con diferencia de precio vs PO
      - Tipo de cambio manual en PO/SO cuando está activo
    """
    _name = 'avco.replay'
    _description = 'Servicio de Replay de AVCO'

    # ------------------------------------------------------------
    # Detección del campo de valor en stock.move
    # (varía entre builds de Odoo 19: value / stock_valuation)
    # ------------------------------------------------------------
    @api.model
    def _get_value_field(self):
        fields_map = self.env['stock.move']._fields
        for candidate in ('value', 'stock_valuation', 'valuation_value', 'account_value'):
            if candidate in fields_map:
                return candidate
        raise UserError(
            "No se detectó el campo de valor en stock.move. "
            "Inspecciona env['stock.move']._fields y agrega el nombre correcto "
            "en AvcoReplay._get_value_field()."
        )

    # ------------------------------------------------------------
    # Conversión de moneda con soporte de TC manual por documento
    # ------------------------------------------------------------
    @api.model
    def _convert_amount(self, amount, from_currency, company, date, document=None):
        """
        Convierte `amount` desde `from_currency` a la moneda de la compañía.

        Si `document` es una orden de compra con TC manual activo, aplica
        `amount / purchase_manual_currency_rate` (equivalente a amount * 1/rate).
        Si `document` es una orden de venta con TC manual activo, aplica
        `amount / sale_manual_currency_rate`.
        En cualquier otro caso usa el TC estándar de Odoo.

        Retorna (converted_amount, rate_label) donde rate_label describe el TC usado.
        """
        company_currency = company.currency_id

        if from_currency == company_currency:
            return amount, f'{company_currency.name}={company_currency.name}'

        # --- TC manual de orden de compra ---
        if document and 'purchase_manual_currency_rate_active' in document._fields.keys():
            if (document.purchase_manual_currency_rate_active
                    and document.currency_id != company_currency):
                rate = document.purchase_manual_currency_rate or 0.0
                if rate > 0:
                    converted = amount / (1/rate)
                    return converted, f'PO-{document.name}-manual({rate:.6f})'

        # --- TC manual de orden de venta ---
        if document and 'sale_manual_currency_rate_active' in document._fields.keys():
            if (document.sale_manual_currency_rate_active
                    and document.currency_id != company_currency):
                rate = document.sale_manual_currency_rate or 0.0
                if rate > 0:
                    converted = amount / (1/rate)
                    return converted, f'SO-{document.name}-manual({rate:.6f})'

        # --- TC estándar de Odoo ---
        converted = from_currency._convert(amount, company_currency, company, date)
        return converted, 'Odoo-std'

    # ------------------------------------------------------------
    # Referencia enriquecida: <orden>/<factura>
    # ------------------------------------------------------------
    @api.model
    def _get_move_ref(self, move):
        """
        Construye la referencia del movimiento como '<orden>/<factura>' cuando
        existen ambos. Soporta compras y ventas. Fallback: origin o picking.
        """
        AML = self.env['account.move.line']
        mf = move._fields

        # --- Compra ---
        if 'purchase_line_id' in mf and move['purchase_line_id']:
            pl = move['purchase_line_id']
            po_name = pl['order_id']['name'] or ''
            bill_line = AML.search([
                ('purchase_line_id', '=', pl['id']),
                ('parent_state', '=', 'posted'),
                ('move_id.move_type', 'in', ('in_invoice', 'in_refund')),
            ], order='date asc', limit=1)
            if bill_line:
                bill = bill_line['move_id']
                bill_ref = bill['ref'] or ''
                ref = f"{po_name}/{bill_ref}/{bill['name']}" if bill_ref else f"{po_name}/{bill['name']}"
                return ref
            return po_name

        # --- Venta (campo opcional si el módulo sale está instalado) ---
        if 'sale_line_id' in mf and move['sale_line_id']:
            sl = move['sale_line_id']
            so_name = sl['order_id']['name'] or ''
            if 'sale_line_ids' in AML._fields:
                inv_line = AML.search([
                    ('sale_line_ids', 'in', [sl['id']]),
                    ('parent_state', '=', 'posted'),
                    ('move_id.move_type', 'in', ('out_invoice', 'out_refund')),
                ], order='date asc', limit=1)
                if inv_line:
                    return f"{so_name}/{inv_line['move_id']['name']}"
            return so_name

        # --- Fallback: origen del documento o nombre del picking ---
        picking_name = ''
        if 'picking_id' in mf and move['picking_id']:
            picking_name = move['picking_id']['name'] or ''
        return move.origin or picking_name or ''

    # ------------------------------------------------------------
    # Landed costs: obtener el monto adicional por unidad para un stock.move
    # ------------------------------------------------------------
    @api.model
    def _get_landed_cost_per_unit(self, move):
        """
        Suma todas las líneas de ajuste de landed cost aplicadas a este move
        (en estado 'done') y retorna el costo adicional por unidad.

        En v19/18 el modelo stock.valuation.adjustment.lines mantiene el vínculo
        entre landed.cost y stock.move con el campo 'additional_landed_cost'.
        """
        AdjLine = self.env.get('stock.valuation.adjustment.lines')
        if AdjLine is None:
            return 0.0
        adj_lines = AdjLine.search([
            ('move_id', '=', move.id),
            ('cost_id.state', '=', 'done'),
        ])
        if not adj_lines or not move.quantity:
            return 0.0
        total_landed = sum(adj_lines.mapped('additional_landed_cost'))
        return total_landed / move.quantity

    # ------------------------------------------------------------
    # Costo unitario de una entrada con TODAS las fuentes consideradas
    # ------------------------------------------------------------
    @api.model
    def _get_incoming_unit_cost(self, move, manual_cost, current_avco, company):
        """
        Orden de prioridad para determinar costo unitario de entrada:
          1) Factura de proveedor ligada al PO → price_unit convertido con TC del PO
             (manual si purchase_manual_currency_rate_active, sino Odoo std)
          2) Línea de PO sin factura → price_unit convertido con TC del PO
          3) Valor ya almacenado en el move (ya está en moneda compañía)
          4) Costo manual (para ajustes manuales sin fuente válida)
          5) AVCO actual (último recurso)

        Retorna (unit_cost_in_company_currency, rate_label).
        """
        value_field = self._get_value_field()
        landed_per_unit = self._get_landed_cost_per_unit(move)

        # --- 1) Factura de proveedor ---
        if move.purchase_line_id:
            po = move.purchase_line_id.order_id
            AccountMoveLine = self.env['account.move.line']
            bill_line = AccountMoveLine.search([
                ('purchase_line_id', '=', move.purchase_line_id.id),
                ('parent_state', '=', 'posted'),
                ('move_id.move_type', 'in', ('in_invoice', 'in_refund')),
            ], order='date asc', limit=1)
            if bill_line and bill_line.price_unit:
                bill_currency = bill_line.move_id.currency_id
                bill_date = bill_line.move_id.invoice_date or bill_line.move_id.date
                # El TC manual se toma del PO que originó la factura
                unit_cost, rate_label = self._convert_amount(
                    bill_line.price_unit, bill_currency, company, bill_date,
                    document=po,
                )
                return unit_cost + landed_per_unit, f'BILL/{rate_label}'

            # --- 2) Línea de PO sin factura ---
            if move.purchase_line_id.price_unit:
                po_currency = po.currency_id
                po_date = po.date_order.date() if po.date_order else move.date
                unit_cost, rate_label = self._convert_amount(
                    move.purchase_line_id.price_unit, po_currency, company, po_date,
                    document=po,
                )
                return unit_cost + landed_per_unit, f'PO/{rate_label}'

        # --- 3) Valor ya en el move (ya está en moneda compañía) ---
        move_val = move[value_field] or 0.0
        if move_val and move.quantity:
            return abs(move_val / move.quantity), 'MOVE-value'

        # --- 4) Ajuste manual ---
        if manual_cost and manual_cost > 0:
            return manual_cost + landed_per_unit, 'MANUAL'

        # --- 5) Último recurso ---
        return current_avco + landed_per_unit, 'AVCO-fallback'

    # ------------------------------------------------------------
    # Obtener AVCO inicial reproduciendo la historia previa a la fecha de corte
    # ------------------------------------------------------------
    @api.model
    def _get_initial_state(self, product, company, date_from, manual_cost):
        """Reproduce moves anteriores a date_from para obtener qty y avco iniciales."""
        prev_moves = self.env['stock.move'].search([
            ('product_id', '=', product.id),
            ('state', '=', 'done'),
            ('date', '<', date_from),
            ('company_id', '=', company.id),
        ], order='date asc, id asc')

        qty = 0.0
        avco = 0.0
        for m in prev_moves:
            src_int = m.location_id.usage == 'internal'
            dst_int = m.location_dest_id.usage == 'internal'
            if dst_int and not src_int:
                unit_cost, _ = self._get_incoming_unit_cost(m, manual_cost, avco, company)
                qty_in = m.quantity
                if qty + qty_in > 0:
                    avco = (qty * avco + qty_in * unit_cost) / (qty + qty_in)
                qty += qty_in
            elif src_int and not dst_int:
                qty -= m.quantity
        return qty, avco

    # ------------------------------------------------------------
    # Replay principal de un producto
    # ------------------------------------------------------------
    @api.model
    def replay_product(self, product, company, date_from, manual_cost,
                       apply=False, rewrite_moves=False):
        """
        Retorna (log, avco_final, qty_final, rows).

        :param product: recordset product.product
        :param company: recordset res.company
        :param date_from: date string 'YYYY-MM-DD'
        :param manual_cost: float, costo para ajustes manuales sin costo propio
        :param apply: bool, si True escribe standard_price
        :param rewrite_moves: bool, si True reescribe value de cada stock.move
        """
        value_field = self._get_value_field()
        log = []
        rows = []

        log.append(f">>> Producto: {product.display_name} (id={product.id})")
        log.append(f">>> Compañía: {company.display_name} | Fecha corte: {date_from}")
        log.append(f">>> Costo manual para ajustes: {manual_cost:.6f}")
        log.append(f">>> Campo de valor detectado: {value_field}")
        log.append("-" * 70)

        # Estado inicial a la fecha de corte
        qty, avco = self._get_initial_state(product, company, date_from, manual_cost)
        log.append(f"[INICIO {date_from}] qty={qty:.4f} avco={avco:.6f}")

        rows.append({
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
        })

        # Moves desde la fecha de corte
        moves = self.env['stock.move'].search([
            ('product_id', '=', product.id),
            ('state', '=', 'done'),
            ('date', '>=', date_from),
            ('company_id', '=', company.id),
        ], order='date asc, id asc')

        for m in moves:
            src_int = m.location_id.usage == 'internal'
            dst_int = m.location_dest_id.usage == 'internal'

            # --- ENTRADA ---
            if dst_int and not src_int:
                qty_before = qty
                avco_before = avco
                unit_cost, rate_label = self._get_incoming_unit_cost(
                    m, manual_cost, avco, company
                )
                landed_per_unit = self._get_landed_cost_per_unit(m)
                qty_in = m.quantity
                new_value = qty_in * unit_cost

                if qty + qty_in > 0:
                    avco = (qty * avco + qty_in * unit_cost) / (qty + qty_in)
                qty += qty_in

                landed_tag = f" (+LC {landed_per_unit:.4f})" if landed_per_unit else ""
                log.append(
                    f"[{m.date}] IN  id={m.id} [{rate_label}] "
                    f"qty_in={qty_in:.4f} unit={unit_cost:.6f}{landed_tag} "
                    f"value={new_value:.4f} "
                    f"→ qty={qty:.4f} avco={avco:.6f}"
                )
                rows.append({
                    'producto': product.display_name,
                    'fecha': str(m.date),
                    'tipo': 'IN',
                    'move_id': m.id,
                    'ref': self._get_move_ref(m),
                    'existencia_anterior': qty_before,
                    'entrada': qty_in,
                    'salida': 0.0,
                    'costo_movimiento': unit_cost,
                    'nuevo_costo': avco,
                    'existencia': qty,
                })

                if apply and rewrite_moves:
                    self._rewrite_move_value(m, new_value, value_field)

            # --- SALIDA ---
            elif src_int and not dst_int:
                qty_before = qty
                avco_before = avco
                qty_out = m.quantity
                new_value = -qty_out * avco
                qty -= qty_out

                log.append(
                    f"[{m.date}] OUT id={m.id} "
                    f"qty_out={qty_out:.4f} avco={avco:.6f} "
                    f"value={new_value:.4f} "
                    f"→ qty={qty:.4f}"
                )
                rows.append({
                    'producto': product.display_name,
                    'fecha': str(m.date),
                    'tipo': 'OUT',
                    'move_id': m.id,
                    'ref': self._get_move_ref(m),
                    'existencia_anterior': qty_before,
                    'entrada': 0.0,
                    'salida': qty_out,
                    'costo_movimiento': avco_before,
                    'nuevo_costo': avco,
                    'existencia': qty,
                })

                if apply and rewrite_moves:
                    self._rewrite_move_value(m, new_value, value_field)

            # --- INTERNO (bodega → bodega): no afecta AVCO ---
            else:
                log.append(
                    f"[{m.date}] INT id={m.id} qty={m.quantity:.4f} "
                    f"(sin impacto en AVCO)"
                )
                rows.append({
                    'producto': product.display_name,
                    'fecha': str(m.date),
                    'tipo': 'INT',
                    'move_id': m.id,
                    'ref': self._get_move_ref(m),
                    'existencia_anterior': qty,
                    'entrada': 0.0,
                    'salida': 0.0,
                    'costo_movimiento': 0.0,
                    'nuevo_costo': avco,
                    'existencia': qty,
                })

        log.append("-" * 70)
        log.append(f"[FINAL] avco_calculado={avco:.6f} qty_final={qty:.4f}")

        # Aplicar standard_price
        if apply:
            if qty > 0:
                product.with_company(company).standard_price = avco
                log.append(f">>> APLICADO: standard_price = {avco:.6f}")
            else:
                log.append(f">>> qty<=0 → standard_price NO modificado")

        return log, avco, qty, rows

    # ------------------------------------------------------------
    # Reescritura forzada del campo value en stock.move
    # ------------------------------------------------------------
    @api.model
    def _rewrite_move_value(self, move, new_value, value_field):
        """
        En Odoo 19 el campo value de stock.move suele estar protegido.
        Usamos SQL directo para forzar la actualización.

        ADVERTENCIA: irreversible. Respalda antes de usar.
        """
        self.env.cr.execute(
            f"UPDATE stock_move SET {value_field} = %s WHERE id = %s",
            (new_value, move.id)
        )
        move.invalidate_recordset([value_field])
