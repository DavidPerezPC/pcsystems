# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import _, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    def _post(self, soft=True):
        # Antes del super, igual que lo hacía Odoo 16: el CFDI se genera después de
        # publicar y tiene que encontrar el pedimento ya escrito en la línea.
        self._ferommis_assign_customs_numbers()
        return super()._post(soft=soft)

    def action_ferommis_assign_customs_numbers(self):
        """Recalcula el pedimento de las facturas seleccionadas.

        Sirve para el caso en que la entrega se validó después de haber publicado la
        factura. Solo tiene efecto sobre el CFDI si todavía no se ha timbrado.
        """
        assigned = self._ferommis_assign_customs_numbers()
        if not assigned:
            raise UserError(_(
                "No se encontró pedimento para ninguna línea. Revise que la entrega esté "
                "validada y que la recepción de la mercancía tenga su costo en destino "
                "con número de pedimento."))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "title": _("Pedimentos asignados"),
                "message": _("Se asignó el pedimento a %s línea(s).", assigned),
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def _ferommis_assign_customs_numbers(self):
        """Escribe el pedimento en las líneas que aún no lo tienen. Devuelve cuántas."""
        lines = self.filtered(
            lambda m: m.is_sale_document() and m.company_id.country_code == "MX"
        ).invoice_line_ids.filtered(
            lambda l: l.display_type == "product"
            and l.product_id
            and not l.l10n_mx_edi_customs_number
        )
        if not lines:
            return 0

        # Un solo recorrido por todas las líneas para no consultar por factura.
        origins_by_line = lines._ferommis_customs_origins()
        all_in_moves = self.env["stock.move"].browse(
            {origin.in_move_id.id for origins in origins_by_line.values() for origin in origins})
        costs_by_move = all_in_moves._ferommis_landed_costs_with_customs()

        assigned = 0
        for line in lines:
            qty_by_number = defaultdict(float)
            for origin in origins_by_line.get(line.id, self.env["ferommis.customs.origin"]):
                cost = costs_by_move.get(origin.in_move_id.id)
                if cost:
                    qty_by_number[cost.l10n_mx_edi_customs_number] += origin.quantity
            if not qty_by_number:
                continue
            # El más representativo primero: es el que el CFDI muestra al principio.
            numbers = sorted(qty_by_number, key=lambda n: (-qty_by_number[n], n))
            line.l10n_mx_edi_customs_number = ",".join(numbers)
            assigned += 1
        return assigned


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _ferommis_customs_origins(self):
        """Capas PEPS que surtieron cada línea de factura, por id de línea."""
        sale_lines = self.sale_line_ids
        if not sale_lines:
            return {}
        origins = self.env["ferommis.customs.origin"].sudo().search([
            ("out_move_id.sale_line_id", "in", sale_lines.ids),
            ("out_move_id.state", "=", "done"),
        ])
        by_sale_line = defaultdict(lambda: self.env["ferommis.customs.origin"].sudo())
        for origin in origins:
            by_sale_line[origin.out_move_id.sale_line_id.id] |= origin

        result = {}
        for line in self:
            matched = self.env["ferommis.customs.origin"].sudo()
            for sale_line in line.sale_line_ids:
                matched |= by_sale_line.get(sale_line.id, matched.browse())
            if matched:
                result[line.id] = matched
        return result
