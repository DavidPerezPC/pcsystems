# -*- coding: utf-8 -*-

from odoo import api, fields, models


class FerommisCustomsOrigin(models.Model):
    """Capa PEPS consumida por una salida de almacén.

    Un renglón por cada recepción de compra de la que salió parte de la mercancía
    entregada. El número de pedimento no se guarda aquí a propósito: se resuelve
    contra el costo en destino en el momento de facturar, porque es frecuente que
    el pedimento se capture días después de que la mercancía ya se entregó.
    """
    _name = "ferommis.customs.origin"
    _description = "Origen PEPS de una salida de almacén"
    _order = "out_move_id, in_move_date, id"
    _rec_name = "in_move_id"

    out_move_id = fields.Many2one(
        "stock.move", string="Salida", required=True, ondelete="cascade", index=True)
    in_move_id = fields.Many2one(
        "stock.move", string="Recepción", required=True, ondelete="cascade", index=True)
    product_id = fields.Many2one(
        "product.product", string="Producto", required=True, index=True)
    quantity = fields.Float(
        string="Cantidad", digits="Product Unit of Measure", required=True,
        help="Cantidad de la salida que proviene de esta recepción, en la unidad de medida del producto.")
    company_id = fields.Many2one(
        "res.company", string="Compañía", required=True, index=True)

    in_move_date = fields.Datetime(
        string="Fecha de recepción", related="in_move_id.date", store=True)
    picking_id = fields.Many2one(
        "stock.picking", string="Albarán de recepción", related="in_move_id.picking_id", store=True)
    landed_cost_id = fields.Many2one(
        "stock.landed.cost", string="Costo en destino",
        compute="_compute_customs", compute_sudo=True)
    customs_number = fields.Char(
        string="Pedimento", compute="_compute_customs", compute_sudo=True)

    @api.depends("in_move_id")
    def _compute_customs(self):
        costs_by_move = self.in_move_id._ferommis_landed_costs_with_customs()
        for origin in self:
            cost = costs_by_move.get(origin.in_move_id.id)
            origin.landed_cost_id = cost
            origin.customs_number = cost.l10n_mx_edi_customs_number if cost else False
