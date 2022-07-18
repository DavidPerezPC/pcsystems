# -*- coding: utf-8 -*-
{
    'name': "Farmer's Credit",

    'summary': """
        Management for Credit issued to farmers""",

    'description': """
        Farmer's Credit needs special administration and flows to control all the 
        operations: Sales Order, Purchase Order, Credit Application, Contracts, 
        Endorsments. 

        This module manages all this in an integrated flow.
    """,

    'author': "PC Systems",
    'website': "http://www.pcsystems.mx",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/14.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Sales',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','account'],

    # always loaded
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/res_partner.xml',
        'views/views.xml',
        'reports/invoice_debt_voucher.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [],
    'qweb': [],
    'auto_install': False,
    'installable': True,
    'application': True,
    'images': ['static/description/farmers_credit_logo.png'],
}
