# -*- coding: utf-8 -*-
{
    'name': "discountlines",

    'summary': """
        Account discount lines""",

    'description': """
        When a discount is given, two entries will be generated. Discount amount is debited to
        the discount account and credited to the Income account (same as proudct)
        NOTE: This account are hardcoded in a dictionary, change to Config Settings Form is recommended
    """,

    'author': "TECNIKA GLOBAL",
    'website': "http://www.tecnika.com.mx",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/14.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Account',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'account'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/account_payment.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
