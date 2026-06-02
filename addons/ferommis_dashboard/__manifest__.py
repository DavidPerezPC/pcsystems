{
    "name": "FEROMMIS Accounting Dashboard",
    "version": "19.0.1.0.0",
    "author": "PC Systems",
    "website": "http://pcsystems.mx",
    "category": "Accounting",
    "summary": "Personalizaciones de KPIs del tablero de Contabilidad para FEROMMIS",
    "description": """
Adapta los 4 KPIs principales del tablero de Contabilidad de Odoo 19:
- Ingreso Actual y Por cobrar: solo diario "Facturas de Cliente".
- Gasto Actual: diarios de compra con contactos etiquetados PROVEEDOR.
- Por pagar: solo contactos etiquetados PROVEEDOR DE MERCANCIAS.
""",
    "depends": ["spreadsheet_dashboard_account_accountant"],
    "data": [
        "data/dashboards.xml",
    ],
    "assets": {
        "spreadsheet.o_spreadsheet": [
            "ferommis_dashboard/static/src/**/*.js",
        ],
    },
    "license": "OPL-1",
    "installable": True,
    "application": False,
}
