# -*- coding: utf-8 -*-
{
    'name': "Petty Cash for Filiales Ley",

    'summary': """
        Links Petty Cash expenses to Account Bank/Cash Statement""",

    'description': """
        Due to Employee Expense App to link DITO to the expense report, this module allows to
        link the Payment (Check o transfer) to the Bank/Cash statements configured with
        Receivable/Payable and reconcile the entries
    """,

    'author': "TECNIKA GLOBAL",
    'website': "http://www.tecnika.com.mx<",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Account',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'account'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/account_payment.xml',
        'views/account_bank_statement.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}