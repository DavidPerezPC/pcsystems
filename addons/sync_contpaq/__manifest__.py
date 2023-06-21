# -*- coding: utf-8 -*-
{
    'name': "sync_contpaq",

    'summary': """
        Sync from Contpaq to Odoo""",

    'description': """
        This module has the business logic to translates Contpaq to Odoo and viceversa
    """,

    'author': "PC Systems",
    'website': "http://pcsystems.mx",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Accounting',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'account'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
        'wizard/sync_import_moves.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
