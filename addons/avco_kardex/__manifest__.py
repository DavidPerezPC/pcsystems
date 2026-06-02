# -*- coding: utf-8 -*-
{
    'name': 'Kardex AVCO',
    'version': '19.0.1.0.0',
    'category': 'Inventory',
    'summary': 'Kardex de inventario con costo promedio ponderado (AVCO)',
    'author': 'PC Systems',
    'depends': [
        'avco_replay',
        'product',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/avco_kardex_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
