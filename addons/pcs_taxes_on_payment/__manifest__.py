{
    "name": "Impuestos sobre Facturas Pagadas",
    "version": "19.0.1.0.0",
    "category": "Accounting",
    "summary": "Cálculo de bases e impuestos por factura efectivamente pagada (cruce SAT)",
    "author": "PCSystems",
    "depends": ["account"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/tax_payment_report_views.xml",
    ],
    "external_dependencies": {"python": ["xlsxwriter"]},
    "license": "LGPL-3",
    "installable": True,
    "application": False,
}
