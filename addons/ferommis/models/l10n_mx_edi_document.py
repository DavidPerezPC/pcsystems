from odoo import api, models
import re


NOVALIDAR = ["SOCIEDAD COOPERATIVA AGUA RODADA S C L"]

class L10nMxEdiDocument(models.Model):
    _inherit = 'l10n_mx_edi.document'

    @api.model
    def _cfdi_sanitize_to_legal_name(self, name):
        if name in NOVALIDAR:
            return name
        else:
            return super(L10nMxEdiDocument, self)._cfdi_sanitize_to_legal_name(name)
