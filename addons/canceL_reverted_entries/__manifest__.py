{
    'name': 'Cancel Reverted Journal Entries',
    'version': '1.0',
    'summary': 'Allows cancellation of reverted journal entries in Odoo.',
    'description': """
        This module provides functionality to cancel journal entries that have been reverted, 
        ensuring better control over accounting records.""",
    'author': 'PC Systems',
    'website': 'http://pcsystems.mx',
    'category': 'Accounting',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/account_move_inverted.xml',
        # Add XML or CSV files here if needed, e.g., 'views/view_file.xml'
    ],
    'installable': True,
    'application': False,
    'license': 'OPL-1',
}