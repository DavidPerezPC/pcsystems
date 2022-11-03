# See LICENSE file for full copyright and licensing details.

{
    "name": "Plan Suarez Synchronization",
    "version": "15.0.1.0.0",
    "category": "Tools",
    "license": "AGPL-3",
    "summary": "To migrate data from one POS App to Odoo",
    "author": "PC Systems",
    "website": "www.pcsystems.mx",
    "maintainer": "PC Systems",
    "images": ["static/description/Synchro.png"],
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "views/plansuarez_synchro_view.xml",
        "wizard/plansuarez_synchro_view.xml",
        "views/res_request_view.xml",
    ],
    "installable": True,
}
