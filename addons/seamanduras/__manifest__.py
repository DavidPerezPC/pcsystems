# -*- coding: utf-8 -*-
{
    'name': "Seamanduras",

    'summary': """
        Seamanduras improvements to fit bussiness' flow""",

    'description': """
        CRM, Customers and Reports adaptations, to comply with Seamanduras requeriments
    """,

    'author': "PC Systems",
    'website': "http://pcsystems.mx",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'CRM',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'crm'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/res_partner.xml',
        'views/crm_lead.xml',       
        'views/views.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
