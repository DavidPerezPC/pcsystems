# -*- coding: utf-8 -*-
# Part of PCSYSTEMS. See LICENSE file for full copyright and licensing details.
{
    'name': 'Product Journal Restrictions',
    'version': '19.0.0.0',
    'category': 'Accounting',
    'summary': 'Restrict products by journal in Purchase Type',
    "description": """ 
 
               Product Journal Restrictions Odoo App helps users to restrict products by journal in Purchase Type. Users can only use allowed product in journal when doing purchase (invoices).

    """,
    'author': 'PC Systems',
    #"price": 15,
    #"currency": 'EUR',
    'website': "https://pcsystems.mx",
    'depends': ['base', 'account', 'purchase'],
    'data': [
        'security/ir.model.access.csv',
        'views/account_journal_views.xml',
    ],
    'license':'OPL-1',
    'installable': True,
    'auto_install': False,
    "images":['static/description/User-Journal-Restrictions-Banner.gif'],
}
