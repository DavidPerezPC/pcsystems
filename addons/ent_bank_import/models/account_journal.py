# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import io
import base64
import csv

STATEMENT_HEADER = ['date', 'ref', 
                    'amount', 
                    'payment_ref', 
                    'partner_name', 
                    'account_number',
                    'statement_id',
                    'unique_import_id'
                ]

class AccountJournal(models.Model):
    _inherit = 'account.journal'

    def _import_bank_statement(self, attachments):
        attach = self._prepare_for_statement_traslations(attachments[0])
        if not attach:
            attach = attachments
        return super()._import_bank_statement(attach)
    
    def _prepare_for_statement_traslations(self, attach):
        options = {
            'has_headers': True,
            'advanced': True,
            'keep_matches': False,
            'name_create_enabled_fields': {},
            'import_set_empty_fields': [],
            'import_skip_records': [],
            'fallback_values': {},
            'skip': 0,        
            'limit': 2000,
            'encoding': 'utf8',
            'separator': ',',
            'quoting': '"',
            'sheet': '',
            'date_format': '',
            'datetime_format': '',
            'float_thousand_separator': ',',
            'float_decimal_separator': '.',
            'fields': [],
            'bank_stmt_import': True 
        }
        bimport = self.env['base_import.import']
        bimport = bimport.create({'file_name': attach.name,
                        'file_type': attach.mimetype,
                        'file': base64.b64decode(attach.datas)
                        })
        reng, content = bimport._read_csv(options)
        content.pop(0)
        cbank = self.bank_id.name.strip().lower()
        cstatement = f"self._{cbank}_statement(content)"
        statement = False
        try:
            statement = eval(cstatement)
        except: 
            pass
        if statement:
            with open('/tmp/empty_statement.csv', 'w', encoding='utf8', newline='') as f:
                writer = csv.writer(f)
                # write the header
                writer.writerow(STATEMENT_HEADER)
                # write multiple rows
                writer.writerows(statement)
            csvfile = open('/tmp/empty_statement.csv', 'rb').read()
            statement = base64.b64encode(csvfile)
            attach.datas = statement
            attach.name = '/tmp/empty_statment.csv'

            return attach
        else:
            return False
               
    def _santander_statement(self, content):

        statement = []
        for row in content:
            sdate = row[1].replace("'","").strip()
            sdate = sdate[-4:] + '-' + sdate[2:4] + '-' + sdate[:2]
            ref = row[8].replace("'","").strip()
            ref2 = row[4].replace("'","").strip()
            if ref and ref2:
                ref = ref + "/" + ref2
            elif ref2:
                ref = ref2
            amountstr = (row[5].strip() + row[6].strip())
            amount = eval(row[5] + row[6]) 
            payment_ref = row[9].replace("'","").strip()
            partner_name = row[11].replace("'","").strip()
            account_number = row[12].replace("'","").strip()
            unique_import_id = f'{sdate.replace("-", "")}_{ref}_{payment_ref}_{amountstr}'
            statement_id = f'{self.name[-4:]} {sdate[:7]}'
            statement.append([sdate, ref, amount, payment_ref, partner_name, 
                              account_number, statement_id, unique_import_id ])

        return statement

    def _scotiabank_statement(self, content):

        statement = []
        for row in content:
            sdate = row[0].replace("/","-").strip()
            ref = row[1].strip()
            ref2 = row[4].strip()
            if ref2:
                ref += "/" + ref2            
            ref2 = row[7].strip()
            if ref2:
                ref += "/" + ref2
            ref2 = row[6].strip()
            amountstr = row[2]
            if row[3] == 'Cargo':
                amountstr = f"-{amountstr}"
            amount = eval(amountstr) 
            payment_ref = row[5].strip() + " " + row[6].strip()
            if not payment_ref.strip():
                payment_ref = ref
            partner_name = False
            account_number = False
            unique_import_id = f'{sdate.replace("-", "")}_{ref}_{payment_ref}_{amountstr}'
            statement_id = f'{self.name[-4:]} {sdate[:7]}'
            statement.append([sdate, ref, amount, payment_ref, partner_name, 
                              account_number, statement_id, unique_import_id ])

        return statement
