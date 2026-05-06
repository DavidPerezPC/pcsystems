import logging
from odoo import models, fields
from odoo.tools import float_is_zero

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    def _get_paid_tax_breakdown(self, date_from=None, date_to=None):
        """
        Desglose de bases e impuestos por pago, usando asientos de base
        de efectivo (CABA) cuando existen, o cálculo proporcional como fallback.
        """
        self.ensure_one()
        result = []

        if self.state != "posted" or self.move_type not in (
            "out_invoice", "out_refund", "in_invoice", "in_refund",
        ):
            return result

        invoice_currency = self.currency_id
        company_currency = self.company_id.currency_id
        is_refund = self.move_type in ("out_refund", "in_refund")
        sign = -1 if is_refund else 1

        receivable_lines = self.line_ids.filtered(
            lambda l: l.account_id.account_type in (
                "asset_receivable", "liability_payable")
        )
        if not receivable_lines:
            return result

        partials = self._get_relevant_partials(
            receivable_lines, date_from, date_to, is_refund)
        if not partials:
            return result

        for partial in partials:
            pay_date = partial.max_date
            paid = self._get_partial_amounts(
                partial, receivable_lines, invoice_currency,
                company_currency, pay_date)

            # Identificar contraparte para el campo informativo
            if partial.debit_move_id in receivable_lines:
                counterpart_move = partial.credit_move_id.move_id
            else:
                counterpart_move = partial.debit_move_id.move_id

            # Base: todos los impuestos proporcionales de la factura
            taxes = self._taxes_proportional(
                partial, paid, sign, invoice_currency, company_currency,
                receivable_lines)

            # Refinamiento: reemplazar con CABA los impuestos que sí lo tienen
            # (on_payment). Los on_invoice quedan del proporcional — ambos quedan.
            caba_moves = self.env["account.move"].search([
                ("tax_cash_basis_rec_id", "=", partial.id),
            ])
            if caba_moves:
                taxes = self._merge_caba_into_taxes(
                    taxes, caba_moves, sign, invoice_currency, company_currency)

            result.append({
                "move_id": self,
                "payment_date": pay_date,
                "paid_amount_currency": invoice_currency.round(
                    paid["currency"] * sign),
                "paid_amount_company": company_currency.round(
                    paid["company"] * sign),
                "exchange_rate": paid["rate"],
                "invoice_currency_id": invoice_currency,
                "company_currency_id": company_currency,
                "counterpart_move": counterpart_move,
                "is_refund": is_refund,
                "taxes": taxes,
            })

        return result

    # ------------------------------------------------------------------
    # Obtención de partials relevantes (sin diferencias cambiarias ni NC)
    # ------------------------------------------------------------------

    def _get_relevant_partials(self, receivable_lines, date_from, date_to,
                                is_refund):
        all_partials = (
            receivable_lines.matched_debit_ids
            | receivable_lines.matched_credit_ids
        )
        exchange_journal = self.company_id.currency_exchange_journal_id
        relevant = self.env["account.partial.reconcile"]

        for partial in all_partials:
            pay_date = partial.max_date
            if date_from and pay_date < fields.Date.to_date(date_from):
                continue
            if date_to and pay_date > fields.Date.to_date(date_to):
                continue

            if partial.debit_move_id in receivable_lines:
                counterpart_line = partial.credit_move_id
            else:
                counterpart_line = partial.debit_move_id

            counterpart_move = counterpart_line.move_id

            # Omitir asientos de diferencia cambiaria
            if (exchange_journal
                    and counterpart_line.journal_id == exchange_journal):
                continue

            # Anti-duplicado NC: la NC se reporta por sí sola con signo negativo
            if not is_refund and counterpart_move.move_type in (
                    "out_refund", "in_refund"):
                continue

            relevant |= partial

        return relevant

    # ------------------------------------------------------------------
    # Montos pagados en la conciliación parcial
    # ------------------------------------------------------------------

    def _get_partial_amounts(self, partial, receivable_lines, invoice_currency,
                              company_currency, pay_date):
        """Monto del partial en moneda factura y moneda compañía."""
        if partial.debit_move_id in receivable_lines:
            inv_amount_currency = partial.debit_amount_currency
        else:
            inv_amount_currency = partial.credit_amount_currency

        amount_company = partial.amount

        if invoice_currency != company_currency and inv_amount_currency:
            amount_currency = inv_amount_currency
        elif invoice_currency == company_currency:
            amount_currency = amount_company
        else:
            amount_currency = company_currency._convert(
                amount_company, invoice_currency, self.company_id, pay_date)

        amount_currency = abs(amount_currency)
        amount_company = abs(amount_company)

        rate = (amount_company / amount_currency
                if not float_is_zero(amount_currency,
                                     precision_rounding=invoice_currency.rounding)
                else 0.0)

        return {"currency": amount_currency, "company": amount_company,
                "rate": rate}

    # ------------------------------------------------------------------
    # Refinamiento CABA: sustituye con valores exactos donde aplica
    # ------------------------------------------------------------------

    def _merge_caba_into_taxes(self, taxes, caba_moves, sign,
                                invoice_currency, company_currency):
        """
        Sustituye valores proporcionales por los exactos del CABA.

        Estrategia por tipo de impuesto:
        - Tasa > 0 (IVA 16%, retenciones, IEPS…):
            monto  → tax_line_id.amount_currency  (ya es proporcional al pago)
            base   → monto ÷ tasa%                (tax_base_amount es el total
                                                   de la factura, no el proporcional)
        - Tasa = 0 (IVA 0%, Exento):
            no tiene tax_line_id (monto=0), se lee de las líneas de base
            del CABA (tax_ids set). Odoo genera una sola línea para estos,
            por eso no se divide entre 2.
        """
        rounding = invoice_currency.rounding
        caba_by_tax = {}

        # --- Paso 1: impuestos con monto (tax_line_id) ---
        # Solo UNA línea por impuesto tiene tax_line_id (la contrapartida no).
        # amount_currency ya es proporcional al pago.
        # tax_base_amount NO es confiable en el CABA: guarda la base total de
        # la factura. La base se obtiene desde las líneas de producto de la
        # factura, proporcional con el mismo ratio implícito del pago:
        #   ratio = tax_cur / tax_total  →  base_cur = base_total * ratio
        for line in caba_moves.line_ids.filtered("tax_line_id"):
            tax = line.tax_line_id
            tax_cur = abs(line.amount_currency)
            tax_comp = abs(line.balance)

            if float_is_zero(tax_cur, precision_rounding=rounding):
                continue

            # Base proporcional: ratio implícito del CABA aplicado a la base total
            tax_total = self._tax_total_from_invoice(tax)
            base_total = self._base_from_product_lines(tax)
            if not float_is_zero(tax_total, precision_rounding=rounding):
                ratio_caba = tax_cur / tax_total
                base_cur = invoice_currency.round(base_total * ratio_caba)
            else:
                base_cur = 0.0

            rate = tax_comp / tax_cur if not float_is_zero(
                tax_cur, precision_rounding=rounding) else 0.0
            base_comp = company_currency.round(base_cur * rate)

            caba_by_tax[tax.id] = {
                "tax_id": tax,
                "tax_name": tax.name,
                "base_amount_currency": invoice_currency.round(base_cur * sign),
                "tax_amount_currency": invoice_currency.round(tax_cur * sign),
                "base_amount_company": company_currency.round(base_comp * sign),
                "tax_amount_company": company_currency.round(tax_comp * sign),
            }

        # --- Paso 2: impuestos tasa 0% / exento (solo líneas de base) ---
        zero_bases = {}

        for line in caba_moves.line_ids.filtered(
                lambda l: l.tax_ids and not l.tax_line_id):
            for tax in line.tax_ids:
                if tax.id in caba_by_tax:
                    continue
                if not float_is_zero(tax.amount, precision_digits=4):
                    continue
                if tax.id not in zero_bases:
                    zero_bases[tax.id] = {
                        "tax": tax, "base_cur": 0.0, "base_comp": 0.0}
                zero_bases[tax.id]["base_cur"] += abs(line.amount_currency)
                zero_bases[tax.id]["base_comp"] += abs(line.balance)

        for tax_id, data in zero_bases.items():
            if not data["tax"]:
                continue
            tax = data["tax"]
            caba_by_tax[tax_id] = {
                "tax_id": tax,
                "tax_name": tax.name,
                "base_amount_currency": invoice_currency.round(
                    data["base_cur"] * sign),
                "tax_amount_currency": 0.0,
                "base_amount_company": company_currency.round(
                    data["base_comp"] * sign),
                "tax_amount_company": 0.0,
            }

        # Sustituir proporcionales con CABA donde exista
        merged = []
        for tax_data in taxes:
            merged.append(caba_by_tax.get(tax_data["tax_id"].id, tax_data))

        # Agregar los que solo están en CABA (no estaban en proporcional)
        existing_ids = {t["tax_id"].id for t in taxes}
        for tax_id, caba_data in caba_by_tax.items():
            if tax_id not in existing_ids:
                merged.append(caba_data)

        return merged

    # ------------------------------------------------------------------
    # Cálculo proporcional (fuente principal para todos los impuestos)
    # ------------------------------------------------------------------

    def _taxes_proportional(self, partial, paid, sign, invoice_currency,
                             company_currency, receivable_lines):
        """
        Calcula base e impuesto proporcionales al pago para TODOS los impuestos
        de la factura, incluyendo los de tasa 0% y exentos que Odoo no registra
        como línea contable porque su monto es cero.
        """
        rounding = invoice_currency.rounding
        total_invoice_currency = sum(
            abs(l.amount_currency) for l in receivable_lines)

        if float_is_zero(total_invoice_currency, precision_rounding=rounding):
            return []

        ratio = paid["currency"] / total_invoice_currency
        taxes = []
        taxes_seen = set()

        # --- Paso 1: impuestos con línea contable (tasa > 0) ---
        for line in self.line_ids.filtered("tax_line_id"):
            tax = line.tax_line_id
            taxes_seen.add(tax.id)

            base_cur = abs(line.tax_base_amount)
            tax_cur = abs(line.amount_currency)

            # Si tax_base_amount no está poblado, lo calcula desde líneas producto
            if float_is_zero(base_cur, precision_rounding=rounding):
                base_cur = self._base_from_product_lines(tax)

            base_cur = invoice_currency.round(base_cur * ratio * sign)
            tax_cur = invoice_currency.round(tax_cur * ratio * sign)
            base_comp = company_currency.round(base_cur * paid["rate"])
            tax_comp = company_currency.round(tax_cur * paid["rate"])

            if (float_is_zero(base_cur, precision_rounding=rounding)
                    and float_is_zero(tax_cur, precision_rounding=rounding)):
                continue

            taxes.append({
                "tax_id": tax,
                "tax_name": tax.name,
                "base_amount_currency": base_cur,
                "tax_amount_currency": tax_cur,
                "base_amount_company": base_comp,
                "tax_amount_company": tax_comp,
            })

        # --- Paso 2: impuestos tasa 0% / exento (no generan línea contable) ---
        # Acumula la base de TODAS las líneas de producto que usan el mismo
        # impuesto 0% antes de agregarlo (evita tomar solo la primera línea).
        zero_tax_bases = {}
        for inv_line in self.invoice_line_ids:
            for tax in inv_line.tax_ids:
                if tax.id in taxes_seen:
                    continue
                if not float_is_zero(tax.amount, precision_digits=4):
                    continue
                if tax.id not in zero_tax_bases:
                    zero_tax_bases[tax.id] = {"tax": tax, "base": 0.0}
                zero_tax_bases[tax.id]["base"] += abs(inv_line.price_subtotal)

        for tax_id, data in zero_tax_bases.items():
            taxes_seen.add(tax_id)
            base_cur = invoice_currency.round(
                data["base"] * ratio * sign)
            base_comp = company_currency.round(base_cur * paid["rate"])

            if float_is_zero(base_cur, precision_rounding=rounding):
                continue

            taxes.append({
                "tax_id": data["tax"],
                "tax_name": data["tax"].name,
                "base_amount_currency": base_cur,
                "tax_amount_currency": 0.0,
                "base_amount_company": base_comp,
                "tax_amount_company": 0.0,
            })

        if not taxes:
            _logger.warning(
                "Factura %s: no se encontraron impuestos. ¿Está publicada?",
                self.name)

        return taxes

    def _base_from_product_lines(self, tax):
        """Base gravable sumando líneas de producto que aplican el impuesto dado."""
        base = 0.0
        for line in self.invoice_line_ids:
            if tax in line.tax_ids:
                base += abs(line.price_subtotal)
        return base

    def _tax_total_from_invoice(self, tax):
        """Monto total del impuesto en la factura (sin prorrateo)."""
        total = 0.0
        for line in self.line_ids.filtered(
                lambda l: l.tax_line_id == tax):
            total += abs(line.amount_currency)
        return total
