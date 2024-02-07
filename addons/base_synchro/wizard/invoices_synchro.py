# See LICENSE file for full copyright and licensing details.

import ssl
import logging
import threading
import time
from xmlrpc.client import ServerProxy
from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _
from odoo.tools import format_datetime
from datetime import datetime

import csv
import base64

_logger = logging.getLogger(__name__)
#company_ids mantiene la relacion entre los ids la compañia:
# origen-destino-diario destino(contrapartida), cuenta de resultados, diario de compras, diarios de ventas
COMPANY_IDS = { 'SVFUSACORP': [5, 13, 378, 8750, 398, 397], 
                'SVFSERVICES': [7 , 14, 390], 
                'MAQ': [4, 15, 392, 19047, 442, 443],
                'OPS': [2, 16, 391, 17241, 440, 441]
                }

JOURNAL_FLDS = {
    'name': 'name',
    'code': 'code',
    'company_id': 'company_id',
    'type': 'type',
    'refund_sequence': 'refund_sequence',
    'currency_id': 'currency_id',
    'sequence': 'sequence',
    'bank_account_id': 'default_account_id',
    'default_debit_account_id': 'default_account_id',
    'default_credit_account_id': 'default_account_id'
                } 

TAX_FLDS = {
    'name': 'name',
    'amount_type': 'amount_type',
    'type_tax_use': 'type_tax_use',
    'amount': 'amount',
    'description': 'description',
    'sequence': 'sequence',
    'tax_group_id': 'tax_group_id',
    'analytic': 'analytic',
    'company_id': 'company_id',
    'invoice_repartition_line_ids': 'invoice_repartition_line_ids',
    'refund_repartition_line_ids': 'refund_repartition_line_ids'
}

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

class RPCProxyTwo(object):

    uid = False
    rpc = False 

    def __init__(self, server):
        """Class to store one RPC proxy server."""
        self.server = server
        context = ssl.SSLContext()
        if server.server_port:
            local_url = "%s:%d/xmlrpc/common" % (
                                server.server_url,
                                server.server_port,
                                )
        else:
            local_url = "%s/xmlrpc/common" % (
                                server.server_url,
                                )            

        #context.update( {'allow_none': True} )
        rpc = ServerProxy(local_url, context=context, allow_none=True)
        #rpc = ServerProxy(local_url, allow_none=True)
        self.uid = rpc.login(server.server_db, server.login, server.password)
        #local_url = "http://%s:%d/xmlrpc/object" % (
        #    server.server_url,
        #    server.server_port if server.server_port else '',
        #)
        #self.rpc = ServerProxy(local_url, context=context)
        local_url = local_url.replace("common", "object")
        self.rpc = ServerProxy(local_url, context=context, allow_none=True)


    def searchread(self, obj, domain, additional=None):

        db = self.server.server_db
        uid = self.uid
        pwd = self.server.password
        rpc = self.rpc

        return rpc.execute_kw(db, uid, pwd, obj, 'search_read', domain, additional )

    def create(self, obj, data):

        db = self.server.server_db
        uid = self.uid
        pwd = self.server.password
        rpc = self.rpc

        return rpc.execute_kw(db, uid, pwd, obj, 'create', [data] )

    def update(self, obj, data):

        db = self.server.server_db
        uid = self.uid
        pwd = self.server.password
        rpc = self.rpc

        return rpc.execute_kw(db, uid, pwd, obj, 'write', data )
    
class RPCProxy2(object):
    """Class to store RPC proxy server."""

    def __init__(self, server):
        self.server = server

    def get(self):
        return RPCProxyTwo(self.server)
    
class SVFSynchro(models.TransientModel):
    """SVF Synchronization."""

    _name = "invoices.synchro"
    _description = "SVF Synchronization"

    @api.model
    def _select_company_balance(self):

        data = [()]
        if self.sync_company:
            balances = self.env['base.synchro.balanza'].search([('id_company', '=', COMPANY_IDS[self.sync_company][0])])
            data = [(balance.id, balance.name) for balance in balances]
        return data

    # source_document = fields.Reference (selection = '_ selection_target_model', 
    # string = "Source Document",
    # compute = "_ compute_sale_order",       
    # inverse = "_ set_sale_order") 

    # def _compute_initial_balance (self):        
    #     order = self.env ['base.synchro.balanza'].search([('id_company', '=', COMPANY_IDS[self.sync_company][0])])        
    #     for rec in self: 
    #         if order: 

    @api.onchange("sync_company")
    def _onchange_sync_company(self):
        for rec in self:
            return {'domain': {'initial_balance': [('id_company', '=', COMPANY_IDS[rec.sync_company][0])]}}

    @api.onchange("sync_obj")
    def _onchange_target_server(self):
        for rec in self:
            return {'domain': {'server_id': [('server_id', '=', self.target_server.id)]}}
    
    @api.depends("server_url")
    def _compute_report_vals(self):
        self.report_total = 0
        self.report_create = 0
        self.report_write = 0

    sync_company = fields.Selection(
        [('SVFUSACORP', 'SVF USA CORP'),
         ('SVFSERVICES', 'SVF SERVICES USA CORP'),
         ('MAQ', 'SVF MAQUINARIA'),
         ('OPS', 'OLYMPIA POWER SYSTEMS')
         ],
         default='MAQ', 
         string='Company',
         help="Select the company to syncronize"
    )
    model_to_sync = fields.Selection(
        [('account.journal', 'Journal'),
         ('account.account', 'Chart of Accounts'),
         ('account.tax', 'Taxes'),
         ('account.move', 'Invoices'), 
         ('initial_balance', 'Initial Balance')
         ]
    )

    initial_balance = fields.Many2one('base.synchro.balanza', 'Balance')

    excel_file = fields.Binary(
        sring='Initial Balance File',
        help="Select the file with the Initial Balance Sheet",
        filters='*.xlsx'
        )
    
    file_name = fields.Char()

    server_url = fields.Many2one(
        "base.synchro.server", "Source Server", required=True
    )
    target_server = fields.Many2one(
        "base.synchro.server", "Target Server", required=True
    )

    sync_obj = fields.Many2one(
        'base.synchro.obj', 'Event Register', required=True
    )

    user_id = fields.Many2one(
        "res.users", "Send Result To", default=lambda self: self.env.user
    )
    report_total = fields.Integer(compute="_compute_report_vals")
    report_create = fields.Integer(compute="_compute_report_vals")
    report_write = fields.Integer(compute="_compute_report_vals")


    @api.model
    def sync_journal(self):

        server = self.server_url
        target = self.target_server
        model = self.model_to_sync
        pool = self
        sync_ids = []
        pool1 = RPCProxy2(server)
        pool2 = RPCProxy2(target)
        src_company = COMPANY_IDS[self.sync_company][0]
        tgt_company = COMPANY_IDS[self.sync_company][1]
        src = pool1.get()
        journals = src.searchread(model,
           [[
               ['company_id', '=', src_company],
               ['active', '=', True]
           ]],
           {'fields': list(JOURNAL_FLDS.keys()), 'order': 'id'}
        )
        tgt = pool2.get()
        
        if not journals:
           raise ValidationError(
               _(
                   """There's no Journals!"""
               )
           )
        _logger.debug(
            "Getting journals to synchronize"
        )

        for journal in journals:
            data = {}
            def_account = False
            for k,v in JOURNAL_FLDS.items():
                fld = journal[k]
                if v == 'company_id':
                    fld = tgt_company
                if k.find('account_id') >= 0:
                    if not def_account:
                        if isinstance(fld, list):
                            fld = fld[0]
                            fld = self._get_account(src, tgt, tgt_company, fld)
                            def_account = fld
                    fld = def_account
                elif isinstance(fld, list):
                    fld = fld[0]
    
                data.update({v: fld})
            id = tgt.create(model, data)
            sync_ids.append([journal['id'], id])
            
        return True

    @api.model
    def sync_balances(self):

        target = self.target_server
        pool2 = RPCProxy2(target)
        src_company = COMPANY_IDS[self.sync_company][0]
        tgt_company = COMPANY_IDS[self.sync_company][1]
        tgt_journal_id = COMPANY_IDS[self.sync_company][2]
        tgt = pool2.get()

        lines = []
        rows = []
        domain = [('id_company', '=', src_company)]
        coa = self.env['base.synchro.account'].search(domain)
        if coa:
            coa = coa[0]
        else:
            return 
        sdate = datetime.strftime(self.initial_balance.date, '%Y-%m-%d')
        first = True
        for line in self.env['base.synchro.balanza.line'].browse(self.initial_balance.account_ids.ids):
            print(f"Linea: {line.account_code, line.debit, line.credit}", end=". ")
            if not line.debit and not line.credit:
                continue

            account = coa.account_ids.filtered(lambda acc: acc.code_alias == line.account_code and acc.account_id_13 > 0)
            print(f"Saldo a Pasar de v13 Cuenta: {account.code_alias} ID {account.account_id_13} a la {account.code_alias_new} ID {account.account_id_16}")
          
            if not account:
                raise Exception(f'La cuenta: {line.account_code} no se encuentra en el COA')
            
            account16 = tgt.searchread('account.account', [[['id', '=', account.account_id_16]]])
            if not account16:
                raise Exception(f'La relacion: {account.code_alias}-{line.account_code} no se encuentra en Odoo 16')
            
            lines.append([0, 0, 
                {
                    'account_id': account.account_id_16,
                    'date': sdate,
                    'name': f'Balanza {self.initial_balance.name}',
                    'debit': line.debit,
                    'credit': line.credit,
                    #'currency_id': 2,
                    #'amount_currency': line.debit or -line.credit 
                }])
            
            if first:
                rows.append([tgt_journal_id, sdate, f'Balanza {self.initial_balance.name}',
                             tgt_company, 'entry', account.account_id_16,
                             f'Balanza {self.initial_balance.name}', line.debit, line.credit]
                            )
                first = False
            else:
                rows.append([ '','' , '', '', '', account.account_id_16, 
                             f'Balanza {self.initial_balance.name}', line.debit, line.credit
                             ])

        header = ['journal_id/id', 'date', 'ref', 'company_id/id', 'move_type', 
                 'line_ids/account_id/id',
                 'line_ids/name',
                 'line_ids/debit',
                 'line_ids/credit'
                 ]
        filename = f'/home/odoo/Balanza_{self.initial_balance.name}.csv'
        with open(filename, 'w', newline="") as file:
            csvwriter = csv.writer(file) # 2. create a csvwriter object
            csvwriter.writerow(header) # 4. write the header
            csvwriter.writerows(rows) # 5. write the rest of the data


        data = {
                'ref': f'Balanza {self.initial_balance.name}', 
                'date': sdate,
                'journal_id': tgt_journal_id,
                'company_id': tgt_company,
                'move_type': 'entry',
                #'currency_id': 2,
                'line_ids': lines
            }
        
        id = tgt.create('account.move', data )
        
        print(f"Poliza Generada con ID: {id}")

        self.initial_balance.write({'odoo_entry_id': id})

        return True



    @api.model
    def sync_accounts(self):

        server = self.server_url
        target = self.target_server
        sync_ids = []
        pool1 = RPCProxy2(server)
        pool2 = RPCProxy2(target)
        src_company = COMPANY_IDS[self.sync_company][0]
        tgt_company = COMPANY_IDS[self.sync_company][1]
        src = pool1.get()
        tgt = pool2.get()
        model = self.model_to_sync

        domain = [('id_company', '=', src_company)]
        coa = self.env['base.synchro.account'].search(domain)
        if coa:
            coa = coa[0]

 
        for line in self.env['base.synchro.account.line'].browse(coa.account_ids.ids):
            print(f"Line: {line.account_code} {line.code_alias} {line.code_alias_new} {line.name}")
            acc_13, acc_16 = self._get_both_accounts(src, tgt, line.code_alias, line.code_alias_new)
            data_local = {} 
            if acc_13 and acc_16: #encontré los dos, actualiza los ids
                data_local = {'account_id_13': acc_13['id'], 'account_id_16': acc_16['id']}
            elif acc_13: 
                data_local = {'account_id_13': acc_13['id'], 'account_id_16': False}
            elif acc_16:
                data_local = {'account_id_16': acc_16['id'], 'account_id_13': False}
            
            line.write(data_local)

            # if (line.code_alias and line.code_alias_new) or not line.code_alias_new:
            # #if not acc_13 and acc_16:
            #     data = [[acc_16['id']], 
            #             {'name': line.name,
            #              'code': line.account_code,
            #              'code_alias': line.code_alias_new if line.code_alias_new else line.code_alias,
            #              'reconcile': line.reconcile, 
            #              'account_type': ACC_TYPES[line.user_type_id]
            #              }]
            #     data_local = {'account_id_13': acc_13['id'], 'account_id_16': acc_16['id']}
            #     #data_local = {'account_id_16': acc_16['id']}
            #     #tgt.update(model, data)
            #     #line.write(data_local)
            #     print(f"Actualizar con {data} y {data_local}")
            # elif not line.code_alias and line.code_alias_new:
            # #elif acc_13 and acc_16:
            
            #     data = {'name': line.name,
            #              'code': line.account_code + '.new',
            #              'code_alias': line.code_alias_new,
            #              'reconcile': line.reconcile, 
            #              'account_type': ACC_TYPES[line.user_type_id],
            #              'company_id': tgt_company
            #             }
            #     #id_16 = tgt.create(model, data)
            #     #data_local = {'account_id_16': id_16}
            #     #data_local = {'account_id_13': acc_13['id'], 'account_id_16': acc_16['id']}
            #     #line.write(data_local)
            #     print(f"Crear {data}" )

            #print(f"Code: {line.account_code}. Alias: {line.code_alias}. New: {line.code_alias_new}. Type: {ACC_TYPES[line.user_type_id]}")

    def _get_account(self, src, tgt, company_id, account_id):
        src_account = src.searchread(
            'account.account',
            [[
                ['id', '=', account_id]
            ]],
            {'fields': ['id', 'name', 'code_alias']}
        )
        tgt_account_id = False
        if src_account:
            src_account = src_account[0]['code_alias']
            tgt_account_id = tgt.searchread(
                    'account.account',
                    [[
                        ['code_alias', '=', src_account],
                        ['company_id', '=', company_id]
                    ]],
                    {'fields': ['id', 'name', 'code_alias']}
            )
            if tgt_account_id:
                tgt_account_id = tgt_account_id[0]['id']
        
        return tgt_account_id

    def _get_both_accounts(self, src, tgt, alias, alias_new):

        src_account = False
        acc_code = False
        if alias:
            src_account = src.searchread(
                'account.account',
                [[
                    ['code_alias', '=', alias],
                    ['company_id', '=', COMPANY_IDS[self.sync_company][0]]
                ]],
                {'fields': ['id', 'name', 'code', 'code_alias', 'user_type_id', 'reconcile']}
            )
            if src_account:
                src_account = src_account[0]

        try:
            if not alias_new and alias[:5] != '10101':
                acc_code = alias
        except:
            pass

        tgt_account_id = False
        code_alias = alias_new or acc_code
        #acc_code = alias
        if code_alias:
            tgt_account_id = tgt.searchread(
                    'account.account',
                    [[
                        ['code_alias', '=', code_alias],
                        ['company_id', '=', COMPANY_IDS[self.sync_company][1]]
                    ]],
                    {'fields': ['id', 'name', 'code', 'code_alias', 'account_type', 'reconcile']}
            )

            if tgt_account_id:
                tgt_account_id = tgt_account_id[0]

        # else:     
        #     tgt_account_id = tgt.searchread(
        #             'account.account',
        #             [[
        #                 ['code', '=', acc],
        #                 ['company_id', '=', COMPANY_IDS[self.sync_company][1]]
        #             ]],
        #             {'fields': ['id', 'name', 'code', 'code_alias', 'account_type', 'reconcile']}
        #     )

        #     if tgt_account_id:
        #         tgt_account_id = tgt_account_id[0]
        
        return src_account, tgt_account_id

    @api.model
    def synchronize(self):

        server = self.server_url
        target = self.target_server
        pool = self
        sync_ids = []
        pool1 = RPCProxy2(server)
        pool2 = RPCProxy2(target)
        src = pool1.get()

        taxes = src.searchread('account.tax',
                               [[
                                   ['company_id', '=', 5],
                                   ['active', '=', True]
                               ]],
                               {'fields': list(TAX_FLDS.keys()), 'order': 'sequence,id' })
        tgt = pool2.get()
        target_customers = tgt.searchread( 'res.partner',  
                                [[['country_id', '=', 156]]],
                                {'fields': ['id', 'name', 'ref', 'vat'], 'order': 'name'}
                            )
        
        if not taxes:
           raise ValidationError(
               _(
                   """No hay facturas en 2021!"""
               )
           )
        _logger.debug(
            "Getting invoices synchronize"
        )
        for inv in taxes:
            print(inv)
            #print(f"Factura: {inv['name']} [{inv['id']}]")
            #self.report_total += 1
            #self.report_write += 1

        for customer in target_customers:
            print(f"Cliente: {customer['name']} [{customer['id']}]")
        
        return True

    def _register_info(self, company_id, src_id, tgt_id, comment=''):

        obj_id = self.sync_obj.id
        scomment = f"Company ID: {company_id}. {comment}"
        data = {
            'name': datetime.now(),
            'obj_id': obj_id,
            'local_id': src_id,
            'remote_id': tgt_id,
            'comments': scomment
        }

        register_id = self.env['base.synchro.obj.line'].create(data)

        return register_id

        # for invoice in invoices:
        #     src_id = invoice['id']
        #     if self.sync_obj.line_id.filtered(lambda invo: invo.local_id == src_id):
        #         continue

        #     domain = [[
        #         ['payment_reference', '=', invoice['name']],
        #         ['move_type', '=', movtotype],
        #         ['company_id', '=', tgt_company]
        #     ]]
        #     invid = tgt.searchread('account.move', domain)
        #     if not invid:
        #         continue
        #     try:
        #         invid = invid[0]['id']
        #         self._uploadfiles(src, tgt, invid, invoice)
        #         self._register_info(tgt_company, invoice['id'], invid, 'Attachment OK')
        #     except Exception as e:
        #         self._register_info(tgt_company, invoice['id'], invid, f"Errror: {repr(e)}")
        #         pass
        #     finally:
        #         break

    @api.model
    def sync_invoices(self, movtotype='in_invoice'):

        server = self.server_url
        target = self.target_server
        model = self.model_to_sync
        pool = self
        sync_ids = []
        pool1 = RPCProxy2(server)
        pool2 = RPCProxy2(target)
        src_company = COMPANY_IDS[self.sync_company][0]
        tgt_company = COMPANY_IDS[self.sync_company][1]
        src = pool1.get()

        #primero los proveedores
        fields = ['id', 'name', 'ref', 'partner_id', 'journal_id', 
                  'date', 'invoice_date', 'invoice_date_due', 'currency_id',
                  'amount_residual', 'amount_total', 
                  'attachment_ids', 'line_ids',
                  'invoice_line_ids'
                ]
       
        invoices = src.searchread(model,
           [[
               ['state', '=', 'posted'],
               ['company_id', '=', src_company],
               ['type', '=', movtotype],
               ['invoice_payment_state', '=', 'not_paid'],
           ]],
           {'fields': fields, 'order': 'name, id'}
        )
        # invoices = src.searchread(model,
        #    [[
        #        #['id', 'in', [279267,392548,471311]]
        #        ['id', 'in', [258846,301497]]
        #    ]],
        #    {'fields': fields, 'order': 'name, id'}
        # )
        tgt = pool2.get()
        
        if not invoices:
           raise ValidationError(
               _(
                   """There's no Invoices!"""
               )
           )
        _logger.debug(
            "Getting invoices to synchronize"
        )

        partners = {}
        journals = {}
        fields = ['id', 'name', 'account_id', 'quantity', 
                  'price_unit', 'debit', 'credit', 'tax_ids']
        
        journal16 = COMPANY_IDS[self.sync_company][4 if movtotype in ('in_invoice', 'in_refund') else 5]

        for invoice in invoices:
            dif_amount = invoice['amount_total'] != invoice['amount_residual']
            print(f"Factura: {invoice['name']}. Fecha: {invoice['date']}")
            partner13 = invoice['partner_id'][0]
            if partner13 in partners.keys():
                partner16 = partners[partner13]
            else:
                partner16 = self._get_partner(src, tgt, partner13)
                partners.update({partner13: partner16})

            journal13 = invoice['journal_id'][0]            
            #journal16 = COMPANY_IDS[self.sync_company][4 if movtotype == 'in_invoice' else 5]
            # if journal13 in journals.keys():
            #     journal16 = journals[journal13]
            # else:
            #     journal16 = self._get_journal(src, tgt, journal13)
            #     journals.update({journal13: journal16})

            lines, linesinv = self.invoice_lines(src, tgt, invoice['line_ids'], invoice['invoice_line_ids'], invoice['currency_id'][0])

            if invoice['date'] > '2023-12-31':
                for line in linesinv:
                    line[2].update({'account_id': COMPANY_IDS[self.sync_company][3]})
                lines = False
    
            data = {
                'company_id': tgt_company,
                'move_type': movtotype,
                'payment_reference': invoice['name'],
                'ref': invoice['ref'], 
                'partner_id': partner16, 
                'journal_id': journal16,
                'date': invoice['date'],
                'currency_id': invoice['currency_id'][0],
                'invoice_date': invoice['date'],
                'invoice_date_due': invoice['invoice_date_due'],
                'invoice_line_ids': linesinv
            }
            try:
                invid = tgt.create('account.move', data)
                # #if invid:
                # #    tgt.update('account.move',[[invid], {'invoice_date': invoice['invoice_date']}])
                # if lines:
                #     #accs = self._get_partner_property_account(tgt, partner16)
                #     acc, new_name = self._get_payable_receivable_invoice(tgt, invid)
                #     for line in lines:
                #         if line[2]['debit'] and line[2]['account_id'] != acc:
                #             line[2].update({'account_id': acc})
    
                #     data.update({
                #                 'date': invoice['date'],
                #                 'partner_id': False,
                #                 'move_type': 'entry', 
                #                 'journal_id': COMPANY_IDS[self.sync_company][2],
                #                 'invoice_line_ids': False,
                #                 'line_ids': lines,
                #                 'ref': f"Contrapartida de: {new_name}. ID:{invid}",
                #                 })
                #     id = tgt.create('account.move', data)
                #self.uploadfiles(self, src, tgt, invoice)
                comment = "Importes diferentes" if dif_amount else "Ok"
                self._uploadfiles(src, tgt, invid, invoice)
                self._register_info(tgt_company, invoice['id'], invid, comment)
                print(f"Factura creada de forma correcta {invoice['name']} con ID {invid}")
            except Exception as e:
                print(f"ERROR en Factura {invoice['name']} con asiento fecha: {invoice['date']}")
                self._register_info(tgt_company, invoice['id'], invid, repr(e))
                pass

        return True

    def _uploadfiles(self, src, tgt, invid, invoice):

        flds13 = [ 'name', 'res_name', 'description', 'type', 
                  'res_id', 'res_model', 'res_name',
                  'db_datas', 'datas', 'store_fname', 
                'mimetype', 'company_id'
                ]
                
        for attch in src.searchread('ir.attachment', 
                                    [[['id', 'in', invoice['attachment_ids']]]],
                                    {'fields': flds13}
                                    ):
                
                content = base64.b64decode(attch['datas'])
                mimetype = attch['mimetype']
                # if attch['mimetype'] == 'application/pdf':
                #     mimetype = 'application/pdf'
                # else:
                #     mimetype = attch['mimetype']
                data = {
                        'name':  attch['name'],
                        'res_name': attch['res_name'],
                        'description': attch['description'],
                        'type': attch['type'],
                        'res_id': invid,
                        'res_model': 'account.move',
                        'datas': base64.encodebytes(content),
                        'mimetype': mimetype,
                        'company_id': COMPANY_IDS[self.sync_company][1],
                    }
                attch_id = tgt.create('ir.attachment', data)

                return attch_id

    def _get_journal(self, src, tgt, journal13):

        fields = ['id', 'name', 'code']
        journal = src.searchread('account.journal', [[['id', '=', journal13]]])[0]
        journal16 = tgt.searchread('account.journal', [[['code', '=', journal['code']]]])[0]['id']

        return journal16

    def _get_payable_receivable_invoice(self, tgt, id, doctype = 'in_invoice'):
 
        invoice = tgt.searchread('account.move', [[['id', '=', id]]], {'fields':['id', 'name', 'line_ids']})
        invoice = invoice[0]
        lines = tgt.searchread('account.move.line', [[['id', 'in', invoice['line_ids']]]], {'fields': ['id', 'debit', 'credit', 'account_id']})
        account_id = False
        for line in lines:
            if doctype == 'in_invoice' and line['credit'] > 0:
                account_id = line['account_id'][0]
                break
            elif doctype == 'out_invoice' and line['debit'] > 0:
                account_id = line['account_id'][0]
                break

        return account_id, invoice['name']


    def _get_partner_property_account(self, tgt, partner):
        accounts = {
           'property_account_payable_id': False,
           'property_account_receivable_id': False 
        }

        domain = [[
                    ['name', 'in', list(accounts.keys())],
                    ['res_id', '=', f'res.partner,{partner}'],
                    ['company_id', '=', COMPANY_IDS[self.sync_company][1]]
                   ]]
        accs = tgt.searchread('ir.property', domain, {'fields': ['id', 'name', 'res_id', 'value_reference', 'company_id']})
        for acc in accs:
            accounts.update({acc['name']: int(acc['value_reference'].replace('account.account,', ''))})
        
        return accounts
    
    def _get_partner(self, src, tgt, partner13):
        fields = ['id', 'name', 'ref', 'vat', 'country_id', 'phone', 'mobile', 'email', 'company_id', 
                'property_account_receivable_id',
                'property_account_payable_id']
        partner = src.searchread('res.partner', [[['id', '=', partner13]]], {'fields': fields})[0]
        for i in range(1,4):
            fld = fields[i]
            value = partner[fld]
            if not value:
                continue
            domain = [[[fld, '=', value]]]
            partner16 = tgt.searchread('res.partner', domain, {'fields': fields})
            if partner16:
                partner16 = partner16[0]
                if partner16['company_id']:
                    tgt.update('res.partner', 
                               [[partner16['id']],
                                 {'company_id': False}
                                 ])
                return partner16['id']
            
        data = {            
            'name': partner['name'],
            'ref': partner['ref'],
            'vat': partner['vat'],
            'country_id': partner['country_id'][0],
            'phone': partner['phone'],
            'mobile': partner['mobile'],
            'email': partner['email'],
 #           'property_account_receivable_id': self._get_inv_account(partner['property_account_receivable_id']),
 #           'property_account_payable_id': self._get_inv_account(partner['proppery_account_payable_id'])
            }

        partner16 = tgt.create('res.partner', data)

        return partner16

    def invoice_lines(self, src, tgt, ids, inv_ids, currency_id):

        fields = ['id', 'name', 'account_id', 'currency_id', 'amount_currency',
                  'quantity', 'price_unit', 'debit', 'credit', 'tax_ids']
        lines = src.searchread('account.move.line', [[['id', 'in', ids]]], {'fields': fields})
        linesinv = src.searchread('account.move.line', [[['id', 'in', inv_ids]]], {'fields': fields})
        lines16 = []
        lines16inv = []
        accounts = {}
        for line in lines:
            account13 = line['account_id'][0]
            if account13 in accounts.keys():
                account16 = accounts[account13]
            else:
                account16 = self._get_inv_account(account13)
                accounts.update({account13: account16})   
            lines16.append([0, 0,
                            {
                                'account_id': account16,
                                'name': line['name'],
                                'debit': line['credit'],
                                'credit': line['debit'],
                                'amount_currency': -line['amount_currency'] if line['amount_currency'] else False,
                                'currency_id': line['currency_id'][0] if line['currency_id'] else currency_id
                            }])
        for line in linesinv:
            account13 = line['account_id'][0]
            if account13 in accounts.keys():
                account16 = accounts[account13]
            else:
                account16 = self._get_inv_account(account13)
                accounts.update({account13: account16})

            taxes = False
            if line['tax_ids']:
                taxes = self._get_taxes(src, tgt, line['tax_ids'])

            lines16inv.append([0, 0,
                {
                    'account_id': account16,
                    'name': line['name'],
                    'quantity': line['quantity'],
                    'price_unit': line['price_unit'],
                    'tax_ids': [[6, 0, taxes]] if taxes else False
                }])
                        
        return lines16, lines16inv
    
    def _get_taxes(self, src, tgt, taxes):

        taxsrc = src.searchread('account.tax', [[['id', 'in', taxes]]])
        taxesname = [x['name'] for x in taxsrc]
        taxtgt = tgt.searchread('account.tax', 
                                [[
                                    ['company_id', '=', COMPANY_IDS[self.sync_company][1]],
                                    ['name', 'in', taxesname]
                                ]])
        taxes = [x['id'] for x in taxtgt]

        return taxes
        
    def _get_inv_account(self, account13):
        company_id = COMPANY_IDS[self.sync_company][0]
        coa = self.env['base.synchro.account'].search([('id_company', '=', company_id)])
        if coa:
            coa = coa[0].account_ids.filtered(lambda acc: acc.account_id_13 == account13)
            account16 = coa.account_id_16
        else:
            raise Exception('La cuenta con ID {account13} no fue encontrado en la compañia {id_company}') 
        
        return account16

    def upload_download(self):
        self.ensure_one()
        report = []
        start_date = fields.Datetime.now()
        timezone = self._context.get("tz", "UTC")
        start_date = format_datetime(
            self.env, start_date, timezone, dt_format=False
        )
        if self.model_to_sync == 'account.journal':
            self.sync_journal()
        elif self.model_to_sync == 'account.account':
            self.sync_accounts()
        elif self.model_to_sync == 'initial_balance':
            self.sync_balances() 
        elif self.model_to_sync == 'account.move':
            self.sync_invoices('in_invoice')
            self.sync_invoices('out_invoice')
            self.sync_invoices('out_refund')
        else:
            self.synchronize()
        # server = self.server_url
        # for obj_rec in server.obj_ids:
        #     _logger.debug("Start synchro of %s", obj_rec.name)
        #     dt = fields.Datetime.now()
        #     self.synchronize(server, obj_rec)
        #     if obj_rec.action == "b":
        #         time.sleep(1)
        #         dt = fields.Datetime.now()
        #     obj_rec.write({"synchronize_date": dt})
        # end_date = fields.Datetime.now()
        # end_date = format_datetime(
        #     self.env, end_date, timezone, dt_format=False
        # )
        # Creating res.request for summary results
    #     if self.user_id:
    #         request = self.env["res.request"]
    #         if not report:
    #             report.append("No exception.")
    #         summary = """Here is the synchronization report:

    #  Synchronization started: %s
    #  Synchronization finished: %s

    #  Synchronized records: %d
    #  Records updated: %d
    #  Records created: %d

    #  Exceptions:
    #     """ % (
    #             start_date,
    #             end_date,
    #             self.report_total,
    #             self.report_write,
    #             self.report_create,
    #         )
    #         summary += "\n".join(report)
    #         request.create(
    #             {
    #                 "name": "Synchronization report",
    #                 "act_from": self.env.user.id,
    #                 "date": fields.Datetime.now(),
    #                 "act_to": self.user_id.id,
    #                 "body": summary,
    #             }
    #         )
    #         return {}

    def upload_download_multi_thread(self):
        threaded_synchronization = threading.Thread(
            target=self.upload_download()
        )
        try:
            threaded_synchronization.run()
        except:
            pass        
        id2 = self.env.ref("base_synchro.view_base_synchro_finish").id
        return {
            "binding_view_types": "form",
            "view_mode": "form",
            "res_model": "base.synchro",
            "views": [(id2, "form")],
            "view_id": False,
            "type": "ir.actions.act_window",
            "target": "new",
        }
