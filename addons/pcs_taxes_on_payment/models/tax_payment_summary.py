from odoo import models, fields, api


MAPPED_TAXES = {
     1: "iva_0_",
     2: "iva_16_",
     5: "ret_isr_arr_",
    19: "iva_exento_",
    24: "iva_8_",
    25: "ret_isr_hon_",
    26: "ret_iva_hon_",
    36: "ret_iva_hon_",
    28: "ret_isr_125_",
    29: "ret_iva_arr_",
    34: "ret_iva_arr_",
    35: "ret_iva_arr_",
    30: "iva_0_",
    31: "ret_iva_4_",
    33: "iva_exento_",
    37: "iva_16_",
    38: "ieps_6_",
}


class TaxPaymentSummary(models.TransientModel):
    _name = "tax.payment.summary"
    _description = "Resumen de Impuestos por Factura Pagada"
    _order = "payment_date, move_id"

    wizard_id = fields.Many2one("tax.payment.report.wizard", ondelete="cascade")

    move_id = fields.Many2one("account.move", string="Factura")
    partner_id = fields.Many2one("res.partner", string="Contacto")
    move_type = fields.Selection(related="move_id.move_type", store=True)
    payment_date = fields.Date(string="Fecha Pago")
    invoice_date = fields.Date(string="Fecha Factura")

    currency_id = fields.Many2one("res.currency", string="Moneda")
    company_currency_id = fields.Many2one("res.currency", string="Moneda Cía.")
    exchange_rate = fields.Float(string="T.C. Pago", digits=(12, 6))

    paid_amount_currency = fields.Monetary(
        string="Pagado (moneda)", currency_field="currency_id")
    paid_amount_company = fields.Monetary(
        string="Pagado (MXN)", currency_field="company_currency_id")

    document_type = fields.Selection([
        ("invoice", "Factura"),
        ("refund", "Nota de Crédito"),
    ], string="Tipo CFDI")
    counterpart_move_id = fields.Many2one(
        "account.move", string="Contraparte",
        help="Pago, NC o reembolso con el que se conció.")

    invoice_uuid = fields.Char(string="UUID Factura", readonly=True)
    counterpart_uuid = fields.Char(string="UUID Abono/NC", readonly=True)

    sat_category = fields.Selection([
        ("iva_trasladado", "IVA Trasladado (Clientes)"),
        ("nc_trasladado", "NC Clientes"),
        ("iva_acreditable", "IVA Acreditable (Proveedores)"),
        ("nc_acreditable", "NC Proveedores"),
    ], string="Categoría SAT", compute="_compute_sat_category", store=True)

    iva_16_base = fields.Float(string="IVA 16% Base", readonly=True)
    iva_16_tax = fields.Float(string="IVA 16% Tax", readonly=True)
    iva_exento_base = fields.Float(string="IVA Exento Base", readonly=True)
    iva_exento_tax = fields.Float(string="IVA Exento Tax", readonly=True)
    iva_0_base = fields.Float(string="IVA 0% Base", readonly=True)
    iva_0_tax = fields.Float(string="IVA 0% Tax", readonly=True)
    iva_8_base = fields.Float(string="IVA 8% Base", readonly=True)
    iva_8_tax = fields.Float(string="IVA 8% Tax", readonly=True)
    ret_iva_4_base = fields.Float(string="Ret IVA 4% Base", readonly=True)
    ret_iva_4_tax = fields.Float(string="Ret IVA 4% Tax", readonly=True)
    ret_iva_hon_base = fields.Float(string="Ret IVA Hon. Base", readonly=True)
    ret_iva_hon_tax = fields.Float(string="Ret IVA Hon. Tax", readonly=True)
    ret_iva_arr_base = fields.Float(string="Ret IVA Arr. Base", readonly=True)
    ret_iva_arr_tax = fields.Float(string="Ret IVA Arr. Tax", readonly=True)
    ret_isr_hon_base = fields.Float(string="Ret ISR Hon. Base", readonly=True)
    ret_isr_hon_tax = fields.Float(string="Ret ISR Hon. Tax", readonly=True)
    ret_isr_arr_base = fields.Float(string="Ret ISR Arr. Base", readonly=True)
    ret_isr_arr_tax = fields.Float(string="Ret ISR Arr. Tax", readonly=True)
    ret_isr_125_base = fields.Float(string="Ret ISR 1.25% Base", readonly=True)
    ret_isr_125_tax = fields.Float(string="Ret ISR 1.25% Tax", readonly=True)
    ieps_6_base = fields.Float(string="Ret IEPS 6% Base", readonly=True)
    ieps_6_tax = fields.Float(string="Ret IEPS 6% Tax", readonly=True)

    unmapped_taxes = fields.Char(
        string="Impuestos sin mapeo",
        readonly=True,
        help="IDs de impuestos encontrados en la factura pero no definidos en MAPPED_TAXES.")

    @api.depends("move_id.move_type")
    def _compute_sat_category(self):
        mapping = {
            "out_invoice": "iva_trasladado",
            "out_refund": "nc_trasladado",
            "in_invoice": "iva_acreditable",
            "in_refund": "nc_acreditable",
        }
        for rec in self:
            rec.sat_category = mapping.get(rec.move_id.move_type, False)
