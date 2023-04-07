# -*- coding: utf-8 -*-
{
    'name': "Caprepa",

    'summary': """
        Caprepa Improvements""",

    'description': """
        Includes improvements to all modules to comply with CaPrepa needs
    """,

    'author': "PC Systems",
    'website': "http://pcsystems.mx",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Tools',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'hr', 'l10n_mx'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/hr_views.xml',
        'views/res_partner_bank.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
