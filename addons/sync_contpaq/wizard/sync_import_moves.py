# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2013 OpenERP s.a. (<http://openerp.com>).
#
#    DME SOLUCIONES
#    Jorge Medina <alfonso.moreno@dmesoluciones.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime as dt, timedelta
#log
import logging
import base64
import io
_logger = logging.getLogger(__name__)


class ImportContpaqMoves(models.TransientModel):
    _name = 'sync.contpaq.import.wizard'

    def _get_default_journal(self, journaldef='PDN'):
        journal = self.env['account.journal'].search([('code', '=', journaldef)])
        return journal.id

    def _get_default_partner(self, partnerdef='Pago nomina'):
        partner = self.env['res.partner'].search([('name', '=', partnerdef)])
        return partner.id
    
    def _get_default_account(self, codedef='210.01.001'):
        account = self.env['account.account'].search([('code', '=', codedef), ('company_id', '=', self.env.company.id)])
        return account.id
    
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        help="Company for this Journal Entries",
        required=True,
        default=lambda self: self.env.company,
        index=True
    )

    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Journal',
        default=lambda self: self._get_default_journal(),
        help='Journal where Entries will be registered',
        domain=[('type', '=', 'general'), ('company_id', '=', company_id)],
        required=True,
    )
    
    account_balance_id = fields.Many2one(
        comodel_name='account.account',
        string='Balance Account',
        help='Account used to Balance the Journal Entries registered',
        default=lambda self: self._get_default_account(),
        domain=[('company_id', '=', company_id)],
        required=True,
    )
    
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Creditor',
        default=lambda self: self._get_default_partner(),
        help='Partner to assign to the Journal Entries registered',
        domain=['|', ('company_id', '=', False), ('company_id', '=', company_id)],
    )

    # upload_file = fields.Binary(
    #     string='File', 
    #     help="Txt File that has the Journal Entry to process")

    # file_name = fields.Char(
    #     string='File name', 
    #     help='Keeps the file selected name'
    # )

    file_ids = fields.Many2many(
        'ir.attachment', 
        'sync_contpaq_import_wizard_attachment_rel',
        'wizar_id', 
        'attachment_id', 
        'File(s)',
        required=True
        )

    def sync_contpaq_journal_entry(self):

        #file = io.BytesIO(base64.b64decode(self.upload_file))
        #base64.decodebytes(self.upload_file)
        am = self.env['account.move']
        acc_rel = self.env['sync.contpaq.account']
        numlin = -1
        ids = []
        action = False

        for file in self.file_ids:
            ml = []
            totcredit = 0
            totdebit = 0
            errmsg = ''
            notes = ''
            lines = file.index_content.split("\n")
            for line in lines:
                numlin += 1
                if line.strip():
                    ltype = line[0:2].strip()                    
                    if ltype == 'P':
                        polizaref = f"({line[18:27].strip()}) {line[40:140].strip()}"
                        date = dt.strftime(dt.strptime(line[3:11], "%Y%m%d"), "%Y-%m-%d")
                        header = {
                            'date':date,
                            'journal_id': self.journal_id.id,
                            'ref': polizaref,
                            'company_id': self.env.company.id,
                        }
                    elif ltype == 'M1':
                        acc_contpaq = line[3:33].strip()
                        accrel   =  acc_rel.search([('code', '=', acc_contpaq), ('company_id', '=', self.company_id.id)])
                        if accrel:
                            account_id = accrel[0].account_id
                            isdebit = (line[65:66].strip() == '0')
                            amount = round(float(line[67:87].strip()),2)                         
                            debit = amount if isdebit else 0.0
                            credit = amount if not isdebit else 0.00
                            amount_currency = line[98:118].strip()
                            partner_id = accrel[0].partner_id.id
                            if not partner_id:
                                partner_id = self.partner_id.id
                            totdebit += debit
                            totcredit+= credit
                            ml.append([0, 0,
                                        {
                                            'account_id': account_id.id,
                                            'name': line[120:220].strip(),
                                            'debit': debit,
                                            'credit': credit,
                                            'partner_id': partner_id,
                                            #'amount_currency': float(amount_currency) if amount_currency else debit + credit,
                                            #'analytc_id': line[221:225].strip()
                                        }])
                        else:
                            errmsg += _(f"Account {acc_contpaq} not found in line: {numlin} of file {file.name}\n") 
                    elif ltype in ['AD', 'AM']:
                        notes += f"{line[3:39]}<br>" 
            if not errmsg:
                if totdebit != totcredit:
                    if totdebit != totcredit:
                        credit = totdebit - totcredit
                        debit = 0.0
                    else:
                        debit = totcredit - totdebit
                        credit = 0.0
                    header.update({'to_check': True})
                    ml.append([0, 0,
                                {
                                    'account_id': self.account_balance_id.id,
                                    'name': _('Move line to force balance'),
                                    'debit': debit,
                                    'credit': credit,
                                    'partner_id': self.partner_id.id,
                                    #'amount_currency': float(amount_currency) if amount_currency else debit + credit,
                                    #'analytc_id': line[221:225].strip()
                                }])                    
                header.update({'line_ids': ml, 'narration': notes if notes else False})
                id = am.create(header)
                ids.append(id.id)
            else:
                raise ValidationError(_(f"Errors on Sync:\n{errmsg}"))

        if ids:
            action = self.env['ir.actions.actions']._for_xml_id('account.action_move_journal_line')
            if len(ids) <= 1 :
                form_view = [(self.env.ref('account.view_move_form').id, 'form')]
                if 'views' in action:
                    action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
                else:
                    action['views'] = form_view
                action['res_id'] = ids[0]
            else:
                action['domain'] = [('id', 'in', ids),('move_type', '=', 'entry')]
            context = {
                'default_move_type': 'entry',
                'default_partner_id': self.partner_id.id,
            }
            action['context'] = context

        return action
        