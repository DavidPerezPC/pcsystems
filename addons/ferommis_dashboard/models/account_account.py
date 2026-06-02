from odoo import api, models
from odoo.fields import Domain

# FEROMMIS rule: when the drill-down list opens for a KPI that targets a
# specific account_type, force the corresponding partner/journal filter even
# if the front-end did not send it (some dashboard click paths bypass the
# audit patch and call spreadsheet_move_line_action with just the codes).
FEROMMIS_AUTO_FILTERS = {
    "liability_payable": {"partner_category_names": ["PROVEEDOR DE MERCANCIAS"]},
    "expense": {
        "partner_category_names": ["PROVEEDOR"],
        "journal_types": ["purchase"],
    },
    "income": {"journal_ids": [1]},
    "income_other": {"journal_ids": [1]},
    "asset_receivable": {"journal_ids": [1]},
}


class AccountAccount(models.Model):
    _inherit = "account.account"

    def _build_spreadsheet_formula_domain(self, formula_params, default_accounts=False):
        domain = super()._build_spreadsheet_formula_domain(
            formula_params, default_accounts=default_accounts
        )

        company_id = formula_params.get("company_id") or self.env.company.id

        journal_ids = [
            int(jid) for jid in formula_params.get("journal_ids", []) if jid
        ]
        journal_types = [
            jtype for jtype in formula_params.get("journal_types", []) if jtype
        ]
        if journal_types:
            type_journal_ids = self.env["account.journal"].search([
                ("type", "in", journal_types),
                ("company_id", "=", company_id),
            ]).ids
            journal_ids = list(set(journal_ids + type_journal_ids)) if journal_ids else type_journal_ids
        if journal_ids:
            domain &= Domain("journal_id", "in", journal_ids)

        partner_category_names = [
            name for name in formula_params.get("partner_category_names", []) if name
        ]
        if partner_category_names:
            categories = self.env["res.partner.category"].search([
                ("name", "in", partner_category_names),
            ])
            if not categories:
                return Domain.FALSE
            partners = self.env["res.partner"].search([
                ("category_id", "in", categories.ids),
            ])
            if not partners:
                return Domain.FALSE
            domain &= Domain("partner_id", "in", partners.ids)

        return domain

    def _ferommis_infer_filters_from_codes(self, args):
        """If ``args`` only carries account codes, infer the FEROMMIS partner
        category / journal filter from the account_type of those codes."""
        if (
            args.get("partner_category_names")
            or args.get("journal_ids")
            or args.get("journal_types")
        ):
            return args
        raw_codes = [c for c in (args.get("codes") or []) if c]
        if not raw_codes:
            return args
        company_id = args.get("company_id") or self.env.company.id
        code_domain = Domain.OR(
            Domain("code", "=like", f"{code}%") for code in raw_codes
        )
        accounts = self.with_company(company_id).search(code_domain)
        types = set(accounts.mapped("account_type"))
        for account_type, overrides in FEROMMIS_AUTO_FILTERS.items():
            if types == {account_type}:
                args = dict(args)
                args.update(overrides)
                return args
        return args

    @api.readonly
    @api.model
    def spreadsheet_move_line_action(self, args):
        args = self._ferommis_infer_filters_from_codes(args)
        return super().spreadsheet_move_line_action(args)

    @api.readonly
    @api.model
    def spreadsheet_fetch_balance_ferommis(self, args_list):
        """Fetch debit/credit/balance for ODOO.BALANCE.FERROMMIS formula.

        Accepts the same args as ``spreadsheet_fetch_debit_credit`` plus the
        optional FEROMMIS filters consumed by
        :meth:`_build_spreadsheet_formula_domain`:
            - journal_ids (list[int|str])
            - journal_types (list[str])
            - partner_category_names (list[str])
        """
        results = []
        for args in args_list:
            company_id = args.get("company_id") or self.env.company.id
            domain = self._build_spreadsheet_formula_domain(args)
            move_lines = self.env["account.move.line"].with_company(company_id)
            [(debit, credit)] = move_lines._read_group(
                domain, aggregates=["debit:sum", "credit:sum"]
            )
            debit = debit or 0.0
            credit = credit or 0.0
            results.append({
                "debit": debit,
                "credit": credit,
                "balance": debit - credit,
            })
        return results
