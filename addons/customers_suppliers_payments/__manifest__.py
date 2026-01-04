# -*- coding: utf-8 -*-

{
    'name': "Customers/Suppliers Payments",
    'version': "19.0.1.0.0",
    'category': 'Accounting',
    'summary': 'This module shows Customers/Suppliers Payments per month',
    'description': "This is helpul for tax declaration within a month. Allows to export"
                   'the payments with the journal entries to Excel file',
    'author': 'PC Systems',
    'company': 'PC Systems',
    'maintainer': 'PC Systems',
    'website': 'http://pcsystems.mx',
    'depends': ['base','l10n_mx_edi'],
    'data': ['security/ir.model.access.csv',
            'views/customers_suppliers_payments_views.xml',
            'wizard/customers_suppliers_payments_wizard.xml',
],
    #'images': ['static/description/banner.jpg'],
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
