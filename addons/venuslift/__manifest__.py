# -*- coding: utf-8 -*-
{
    'name': "Venus Lift",

    'summary': """
        Enhanced features and funcionality for VenusLift""",

    'description': """
        Features to improve process and validation in the workflows:
        Sales
        Accouting
        Purchases
    """,

    'author': "PC Systems",
    'website': "http://www.pcsystems.mx",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/14.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','account', 'sale', 'stock', 'mail'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/res_partner.xml',
        'views/stock.xml',
        'views/sale_order.xml',
        'views/account_payment.xml',        
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
