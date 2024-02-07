# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class BalanzaSyncro(models.Model):
    """Para guardar las balanzas"""

    _name = "base.synchro.balanza"
    _description = "Balance Syncronization"

    name = fields.Char("Company name", required=True)
    id_company = fields.Integer("Company ID", required=True)
    date = fields.Date("Balance Date")
    account_ids = fields.One2many(
        "base.synchro.balanza.line", "balanza_id", "Accounts", ondelete="cascade"
    )
    odoo_entry_id = fields.Integer("ID Odoo")

class BalanzaSyncroLine(models.Model):
    """Class to store balance lines"""

    _name = "base.synchro.balanza.line"
    _description = "Balanza Lines"
    _order = "account_code"

    name = fields.Char(required=True)
    balanza_id = fields.Many2one(
        "base.synchro.balanza", "Balanza", ondelete="cascade", required=True
    )
    account_code = fields.Char("Account")
    debit = fields.Float("Debit")
    credit = fields.Float("Credit")

