import io
import base64
import logging
from collections import defaultdict
from datetime import datetime, time

import xlsxwriter

from odoo import models, fields, _
from odoo.exceptions import UserError
from odoo.addons.pcs_taxes_on_payment.models.tax_payment_summary import MAPPED_TAXES

_logger = logging.getLogger(__name__)


TAX_COLUMNS = [
    ("iva_16", "IVA 16%"),
    ("iva_8", "IVA 8%"),
    ("iva_0", "IVA 0%"),
    ("iva_exento", "IVA Exento"),
    ("ret_iva_4", "Ret IVA 4%"),
    ("ret_iva_hon", "Ret IVA Hon"),
    ("ret_iva_arr", "Ret IVA Arr"),
    ("ret_isr_hon", "Ret ISR Hon"),
    ("ret_isr_arr", "Ret ISR Arr"),
    ("ret_isr_125", "Ret ISR 1.25"),
    ("ieps_6", "IEPS 6"),
]

SAT_CATEGORY_LABELS = {
    "iva_trasladado": "IVA Trasladado (Clientes)",
    "nc_trasladado": "NC Clientes",
    "iva_acreditable": "IVA Acreditable (Proveedores)",
    "nc_acreditable": "NC Proveedores",
}


class TaxPaymentReportWizard(models.TransientModel):
    _name = "tax.payment.report.wizard"
    _description = "Reporte de Impuestos sobre Pagos"

    payment_date_from = fields.Date(
        string="Fecha Pago Desde", required=True,
        default=lambda s: fields.Date.context_today(s).replace(day=1))
    payment_date_to = fields.Date(
        string="Fecha Pago Hasta", required=True,
        default=fields.Date.context_today)
    move_type = fields.Selection([
        ("all", "Ambos (Clientes y Proveedores)"),
        ("customer", "Sólo Clientes"),
        ("supplier", "Sólo Proveedores"),
    ], default="all", required=True)
    partner_ids = fields.Many2many("res.partner", string="Contactos")
    use_mxn = fields.Boolean(
        string="Importes en MXN",
        default=True,
        help="Si está activo, columnas base/tax en moneda compañía al T.C. del pago.")
    summary_ids = fields.One2many("tax.payment.summary", "wizard_id")

    xlsx_file = fields.Binary(string="Archivo XLSX", readonly=True)
    xlsx_filename = fields.Char(readonly=True)

    def action_compute(self):
        self.ensure_one()
        if self.payment_date_from > self.payment_date_to:
            raise UserError(_("La fecha inicial no puede ser mayor que la final."))

        self.summary_ids.unlink()
        moves = self._find_paid_moves_in_range()

        vals_list = []
        for move in moves:
            breakdown = move._get_paid_tax_breakdown(
                self.payment_date_from, self.payment_date_to)
            for event in breakdown:
                vals_list.append((0, 0, self._build_summary_row(move, event)))

        self.summary_ids = vals_list
        return {
            "type": "ir.actions.act_window",
            "res_model": "tax.payment.report.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _find_paid_moves_in_range(self):
        type_map = {
            "customer": ("out_invoice", "out_refund"),
            "supplier": ("in_invoice", "in_refund"),
            "all": ("out_invoice", "out_refund", "in_invoice", "in_refund"),
        }
        move_types = type_map[self.move_type]

        partial_domain = [
            ("max_date", ">=", self.payment_date_from),
            ("max_date", "<=", self.payment_date_to),
        ]
        partials = self.env["account.partial.reconcile"].search(partial_domain)
        if not partials:
            return self.env["account.move"]

        lines = partials.debit_move_id | partials.credit_move_id
        move_ids = lines.move_id.ids

        domain = [
            ("id", "in", move_ids),
            ("state", "=", "posted"),
            ("move_type", "in", move_types),
        ]
        if self.partner_ids:
            domain.append(("partner_id", "in", self.partner_ids.ids))

        return self.env["account.move"].search(domain, order="invoice_date, name")

    def _build_summary_row(self, move, event):
        base_key = "base_amount_company" if self.use_mxn else "base_amount_currency"
        tax_key = "tax_amount_company" if self.use_mxn else "tax_amount_currency"

        row = {
            "move_id": move.id,
            "partner_id": move.partner_id.id,
            "payment_date": event["payment_date"],
            "invoice_date": move.invoice_date,
            "currency_id": event["invoice_currency_id"].id,
            "company_currency_id": event["company_currency_id"].id,
            "exchange_rate": event["exchange_rate"],
            "paid_amount_currency": event["paid_amount_currency"],
            "paid_amount_company": event["paid_amount_company"],
            "document_type": "refund" if event["is_refund"] else "invoice",
            "counterpart_move_id": event["counterpart_move"].id,
        }

        for prefix in set(MAPPED_TAXES.values()):
            row[prefix + "base"] = 0.0
            row[prefix + "tax"] = 0.0

        unmapped = []
        for tax_data in event["taxes"]:
            tax_id = tax_data["tax_id"].id
            prefix = MAPPED_TAXES.get(tax_id)
            if not prefix:
                unmapped.append("id=%s (%s)" % (tax_id, tax_data["tax_name"]))
                _logger.warning(
                    "Factura %s: impuesto id=%s (%s) no está en MAPPED_TAXES",
                    move.name, tax_id, tax_data["tax_name"],
                )
                continue
            row[prefix + "base"] += tax_data[base_key]
            row[prefix + "tax"] += tax_data[tax_key]

        if unmapped:
            row["unmapped_taxes"] = ", ".join(unmapped)

        return row

    def action_export_xlsx(self):
        self.ensure_one()
        if not self.summary_ids:
            self.action_compute()

        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {"in_memory": True})

        fmt_header = workbook.add_format({
            "bold": True, "bg_color": "#305496", "font_color": "white",
            "border": 1, "align": "center",
        })
        fmt_money = workbook.add_format({"num_format": "#,##0.00"})
        fmt_money_total = workbook.add_format({
            "num_format": "#,##0.00", "bold": True, "top": 2,
            "bg_color": "#D9E1F2",
        })
        fmt_date = workbook.add_format({"num_format": "yyyy-mm-dd"})
        fmt_rate = workbook.add_format({"num_format": "#,##0.000000"})

        for category, label in SAT_CATEGORY_LABELS.items():
            rows = self.summary_ids.filtered(lambda r: r.sat_category == category)
            self._write_sheet(workbook, label[:31], rows, fmt_header,
                              fmt_money, fmt_money_total, fmt_date, fmt_rate)

        self._write_summary_sheet(workbook, fmt_header, fmt_money, fmt_money_total)

        workbook.close()
        data = base64.b64encode(buffer.getvalue())
        buffer.close()

        filename = "impuestos_pagos_%s_%s.xlsx" % (
            self.payment_date_from, self.payment_date_to)
        self.write({"xlsx_file": data, "xlsx_filename": filename})

        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/?model=%s&id=%d&field=xlsx_file"
                   "&filename_field=xlsx_filename&download=true"
                   % (self._name, self.id),
            "target": "self",
        }

    def _write_sheet(self, wb, name, rows, fmt_h, fmt_m, fmt_mt, fmt_d, fmt_r):
        sheet = wb.add_worksheet(name)
        headers = [
            ("Fecha Pago", 12), ("Factura", 15), ("Fecha Factura", 12),
            ("Contacto", 30), ("RFC", 15), ("Contraparte", 15),
            ("Moneda", 8), ("T.C.", 10),
            ("Pagado Moneda", 14), ("Pagado MXN", 14),
        ]
        for code, label in TAX_COLUMNS:
            headers.append((label + " Base", 14))
            headers.append((label, 14))

        for col, (label, width) in enumerate(headers):
            sheet.write(0, col, label, fmt_h)
            sheet.set_column(col, col, width)
        sheet.freeze_panes(1, 0)

        totals = defaultdict(float)
        row_idx = 1
        for rec in rows:
            if rec.payment_date:
                sheet.write_datetime(row_idx, 0,
                    datetime.combine(rec.payment_date, time.min), fmt_d)
            sheet.write(row_idx, 1, rec.move_id.name or "")
            if rec.invoice_date:
                sheet.write_datetime(row_idx, 2,
                    datetime.combine(rec.invoice_date, time.min), fmt_d)
            sheet.write(row_idx, 3, rec.partner_id.name or "")
            sheet.write(row_idx, 4, rec.partner_id.vat or "")
            sheet.write(row_idx, 5, rec.counterpart_move_id.name or "")
            sheet.write(row_idx, 6, rec.currency_id.name or "")
            sheet.write(row_idx, 7, rec.exchange_rate, fmt_r)
            sheet.write(row_idx, 8, rec.paid_amount_currency, fmt_m)
            sheet.write(row_idx, 9, rec.paid_amount_company, fmt_m)

            col = 10
            for code, _label in TAX_COLUMNS:
                base_val = getattr(rec, code + "_base")
                tax_val = getattr(rec, code + "_tax")
                sheet.write(row_idx, col, base_val, fmt_m)
                sheet.write(row_idx, col + 1, tax_val, fmt_m)
                totals[code + "_base"] += base_val
                totals[code + "_tax"] += tax_val
                col += 2

            totals["paid_currency"] += rec.paid_amount_currency
            totals["paid_company"] += rec.paid_amount_company
            row_idx += 1

        if row_idx > 1:
            sheet.write(row_idx, 0, "TOTAL", fmt_mt)
            sheet.write(row_idx, 8, totals["paid_currency"], fmt_mt)
            sheet.write(row_idx, 9, totals["paid_company"], fmt_mt)
            col = 10
            for code, _label in TAX_COLUMNS:
                sheet.write(row_idx, col, totals[code + "_base"], fmt_mt)
                sheet.write(row_idx, col + 1, totals[code + "_tax"], fmt_mt)
                col += 2

    def _write_summary_sheet(self, wb, fmt_h, fmt_m, fmt_mt):
        sheet = wb.add_worksheet("Resumen SAT")
        sheet.set_column(0, 0, 35)
        sheet.set_column(1, len(TAX_COLUMNS) * 2, 14)

        sheet.write(0, 0, "Categoría SAT", fmt_h)
        col = 1
        for _code, label in TAX_COLUMNS:
            sheet.write(0, col, label + " Base", fmt_h)
            sheet.write(0, col + 1, label, fmt_h)
            col += 2

        category_totals = {cat: defaultdict(float) for cat in SAT_CATEGORY_LABELS}
        for rec in self.summary_ids:
            if not rec.sat_category:
                continue
            for code, _label in TAX_COLUMNS:
                category_totals[rec.sat_category][code + "_base"] += \
                    getattr(rec, code + "_base")
                category_totals[rec.sat_category][code + "_tax"] += \
                    getattr(rec, code + "_tax")

        row = 1
        for cat, label in SAT_CATEGORY_LABELS.items():
            sheet.write(row, 0, label)
            col = 1
            for code, _l in TAX_COLUMNS:
                sheet.write(row, col, category_totals[cat][code + "_base"], fmt_m)
                sheet.write(row, col + 1, category_totals[cat][code + "_tax"], fmt_m)
                col += 2
            row += 1

        sheet.write(row, 0, "NETO A PAGAR / (A FAVOR)", fmt_mt)
        col = 1
        for code, _l in TAX_COLUMNS:
            net_base = (
                category_totals["iva_trasladado"][code + "_base"]
                + category_totals["nc_trasladado"][code + "_base"]
                - category_totals["iva_acreditable"][code + "_base"]
                - category_totals["nc_acreditable"][code + "_base"]
            )
            net_tax = (
                category_totals["iva_trasladado"][code + "_tax"]
                + category_totals["nc_trasladado"][code + "_tax"]
                - category_totals["iva_acreditable"][code + "_tax"]
                - category_totals["nc_acreditable"][code + "_tax"]
            )
            sheet.write(row, col, net_base, fmt_mt)
            sheet.write(row, col + 1, net_tax, fmt_mt)
            col += 2
