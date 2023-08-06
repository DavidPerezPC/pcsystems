# -*- coding: utf-8 -*-
{
    'name': "Bank Statements Import for México",

    'summary': """
        Helper to Import Mexican Banks statements""",

    'description': """
        This module imports the CSV Statements generated for each bank. 

        Each bank has its onw logic
    """,

    'author': "PC Systems",
    'website': "pcsystems.mx",
    "license": "AGPL-3",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Banking addons',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['account_bank_statement_import_csv'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
    ],
    'installable': True,
}
