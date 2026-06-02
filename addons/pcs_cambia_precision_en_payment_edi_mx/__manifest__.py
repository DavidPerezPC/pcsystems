{
    'name': 'PCS - Cambia Precisión en Payment EDI MX',
    'version': '19.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Cambia la precisión de BaseP e ImporteP de 6 a 2 decimales en el XML de complemento de pago',
    'depends': ['l10n_mx_edi'],
    'data': [
        'data/payment20_patch.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
