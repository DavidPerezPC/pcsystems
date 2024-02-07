# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

ACC_TYPES = {
        "Receivable": "asset_receivable",
        "Bank and Cash": "asset_cash",
        "Current Assets": "asset_current",
        "Non-current Assets": "asset_non_current",
        "Prepayments": "asset_prepayments",
        "Fixed Assets": "asset_fixed",
        "Payable": "liability_payable",
        "Credit Card": "liability_credit_card",
        "Current Liabilities": "liability_current",
        "Non-current Liabilities": "liability_non_current",
        "Equity": "equity",
        "Current Year Earnings": "equity_unaffected",
        "Income": "income",
        "Other Income": "income_other",
        "Expenses": "expense",
        "Depreciation": "expense_depreciation",
        "Cost of Revenue": "expense_direct_cost",
        "Off-Balance Sheet": "off_balance",
}

class AccountSyncro(models.Model):
    """Para guardar las cuentas"""

    _name = "base.synchro.account"
    _description = "Balance Syncronization"

    name = fields.Char("Company name", required=True)
    id_company = fields.Integer("Company ID", required=True)
    account_ids = fields.One2many(
        "base.synchro.account.line", "coa_id", "Accounts", ondelete="cascade"
    )


class AccountSyncroLine(models.Model):
    """Class to store account lines"""

    _name = "base.synchro.account.line"
    _description = "Account Lines"
    _order = "account_code"

    name = fields.Char(required=True)
    coa_id = fields.Many2one(
        "base.synchro.account", "COA", ondelete="cascade", required=True
    )
    account_code = fields.Char("Account")
    external_id = fields.Char("External ID")
    code_alias = fields.Char("Alias")
    code_alias_new = fields.Char("New Alias")
    user_type_id = fields.Char("Type")
    reconcile = fields.Boolean("Reconcile")
    currency_id = fields.Char("Currency")
    account_id_13 = fields.Integer("ID v13")
    account_id_16 = fields.Integer("ID v16")
