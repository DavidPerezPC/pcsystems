# -*- coding: utf-8 -*-
{
    'name': "Finkok Stamps",

    'summary': """
        Module for manage Fiscal Stamps with Finkok by Customer""",

    'description': """
        This module is a helper to invoice SAT Stamps by RFC
    """,

    'author': "PC Systems",
    'website': "http://pcsystems.mx",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Sales',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'sale_management', 'account'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'wizard/stamps_import_wizard.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
