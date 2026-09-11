# -*- coding: utf-8 -*-
{
    "name": "FEROMMIS - Pedimentos por PEPS",
    "version": "19.0.1.0.0",
    "author": "PC Systems",
    "website": "http://pcsystems.mx",
    "category": "Accounting/Localizations/EDI",
    "summary": "Asigna el número de pedimento a las facturas siguiendo la capa PEPS de la entrega",
    "description": """
Repone el automatismo que Odoo 16 traía de fábrica en l10n_mx_edi_landing y que
Odoo 19 sustituyó por un mecanismo basado en lotes.

Al validar una entrega se registra de qué recepciones de compra salió la mercancía,
siguiendo el mismo orden PEPS que usa la valuación de Odoo. Al publicar la factura,
el número de pedimento del costo en destino de esas recepciones se copia a la línea.

No exige lotes, ni valuación por lote, ni facturar por cantidad entregada, ni
modifica el costeo de los productos.
""",
    "depends": [
        "stock_account",
        "l10n_mx_edi_landing",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_actions_server.xml",
        "views/ferommis_customs_origin_views.xml",
    ],
    "license": "OPL-1",
    "installable": True,
    "application": False,
}
