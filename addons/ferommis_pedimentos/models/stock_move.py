# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    ferommis_customs_origin_ids = fields.One2many(
        "ferommis.customs.origin", "out_move_id", string="Origen PEPS", readonly=True)
    ferommis_customs_number = fields.Char(
        string="Pedimentos", compute="_compute_ferommis_customs_number", compute_sudo=True,
        help="Pedimentos de las recepciones de las que salió esta mercancía, según la capa PEPS.")

    @api.depends("ferommis_customs_origin_ids")
    def _compute_ferommis_customs_number(self):
        for move in self:
            numbers = move.ferommis_customs_origin_ids.filtered("customs_number").mapped("customs_number")
            move.ferommis_customs_number = ", ".join(dict.fromkeys(numbers)) or False

    # -------------------------------------------------------------------------
    # CAPTURA DEL ORIGEN PEPS
    # -------------------------------------------------------------------------

    def _action_done(self, cancel_backorder=False):
        # La pila PEPS se arma a partir de la existencia actual, así que hay que leerla
        # ANTES de que el movimiento se marque como hecho. Es el mismo motivo por el que
        # stock_account calcula aquí el valor de las salidas.
        origin_vals = self._ferommis_prepare_customs_origins()
        moves = super()._action_done(cancel_backorder=cancel_backorder)
        if origin_vals:
            # _action_done puede partir, cancelar o borrar movimientos (entregas parciales),
            # así que solo se guarda el origen de los que quedaron efectivamente hechos.
            done = set((self.exists() | moves).filtered(lambda m: m.state == "done").ids)
            vals_list = [vals for vals in origin_vals if vals["out_move_id"] in done]
            if vals_list:
                self.env["ferommis.customs.origin"].sudo().create(vals_list)
        return moves

    def _ferommis_prepare_customs_origins(self):
        """Reparte la cantidad de cada salida entre las recepciones que la surten."""
        candidates = self.filtered(lambda m: m._ferommis_needs_customs_origin())
        if not candidates:
            return []

        vals_list = []
        for company, moves in candidates.grouped("company_id").items():
            # Odoo valúa varias salidas del mismo producto en una sola validación
            # descontándolas de la pila una tras otra; hay que llevar la misma cuenta.
            processed = defaultdict(float)
            for move in moves:
                product = move.product_id.with_company(company)
                pending = move._get_valued_qty()
                if product.uom_id.compare(pending, 0) <= 0:
                    continue

                stack, qty_on_first = product.with_context(
                    fifo_qty_already_processed=processed[product]
                )._run_fifo_get_stack()
                processed[product] += pending

                for index, in_move in enumerate(stack):
                    if product.uom_id.compare(pending, 0) <= 0:
                        break
                    if index == 0 and qty_on_first:
                        available = qty_on_first
                    else:
                        available = in_move._get_valued_qty()
                    if product.uom_id.compare(available, 0) <= 0:
                        continue
                    taken = min(pending, available)
                    pending -= taken
                    vals_list.append({
                        "out_move_id": move.id,
                        "in_move_id": in_move.id,
                        "product_id": move.product_id.id,
                        "quantity": taken,
                        "company_id": company.id,
                    })
        return vals_list

    def _ferommis_needs_customs_origin(self):
        """Solo entregas de venta de una compañía mexicana."""
        self.ensure_one()
        return bool(
            self.sale_line_id
            and not self.scrap_id
            and self.company_id.country_code == "MX"
            and self.product_id.is_storable
            and self.state not in ("done", "cancel")
            and self._is_out()
        )

    # -------------------------------------------------------------------------
    # RESOLUCIÓN DEL PEDIMENTO
    # -------------------------------------------------------------------------

    def _ferommis_landed_costs_with_customs(self):
        """Costo en destino con pedimento de cada recepción, por movimiento de entrada.

        Se busca por línea de ajuste de valuación y no por albarán: un costo en destino
        puede amparar un albarán con productos que no entraron en su reparto, y
        atribuirles el pedimento sería incorrecto ante una auditoría.
        """
        if not self:
            return {}
        adjustments = self.env["stock.valuation.adjustment.lines"].sudo().search(
            [
                ("move_id", "in", self.ids),
                ("cost_id.state", "=", "done"),
                ("cost_id.l10n_mx_edi_customs_number", "!=", False),
            ],
            order="cost_id, id",
        )
        costs_by_move = {}
        for adjustment in adjustments:
            costs_by_move.setdefault(adjustment.move_id.id, adjustment.cost_id)
        return costs_by_move
