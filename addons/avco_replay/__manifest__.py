# -*- coding: utf-8 -*-
{
    'name': 'AVCO Replay - Recálculo histórico de costo promedio',
    'version': '19.0.1.0.0',
    'category': 'Inventory',
    'summary': 'Reconstruye el costo promedio (AVCO) replayando stock.move '
               'con soporte para landed costs y ajustes manuales sin costo.',
    'description': """
AVCO Replay
===========
Permite recalcular el costo promedio de productos desde una fecha específica,
reproduciendo toda la historia de stock.move en orden cronológico.

Características:
* Replay cronológico desde fecha de corte configurable
* Costo manual por producto para ajustes sin costo propio
* Soporte completo de landed costs (costos en destino)
* Modo simulación (dry-run) con log detallado antes de aplicar
* Reescritura opcional del campo value en stock.move
* Detección automática del campo de valor según build de v19
    """,
    'author': 'Custom',
    'depends': [
        'stock',
        'purchase',
        'stock_landed_costs',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/avco_replay_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
