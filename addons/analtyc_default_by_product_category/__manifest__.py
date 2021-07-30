# -*- coding: utf-8 -*-
{
    'name': "Analytic Default Extension",

    'summary': """
        Add Product Category to Analytic Account Rules""",

    'description': """
        By default Analtyic Account Rules logic includes Product ID, this module adds logic
        to use Category ID in the rule; additionally takes the Comercial from the invoice not from 
        active user 
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
        'views/account_analytic_default.xml',
    ],
    # only loaded in demonstration mode,
}
