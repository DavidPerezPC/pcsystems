# -*- coding: utf-8 -*-
{
    'name': "AUPA",

    'summary': """
        Adapt for AUPA business flow""",

    'description': """
        Adds year and harvest in Analytic Accounts and allows automation for Invoicing.
    """,

    'author': "PC Systems",
    'website': "http://www.pcsystems.mx",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/14.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'PC Systems',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['account'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/analytic_account_views.xml',
        'views/product_product_views.xml',
        'views/account_move_views.xml',
        'wizard/account_move_wizard.xml',
        'views/templates.xml',
        #'views.xml'
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
