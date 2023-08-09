import logging
from odoo import models, fields


_logger = logging.getLogger(__name__)

class ResBranch(models.Model):
    _inherit = 'res.branch'
    _order = 'code, id'

    brand_id = fields.Many2one(
        comodel_name='caprepa.brands',
        string="Brand",
        help="Select the Brand for this Branch",
        tracking=1,
        domain="[('parent_id', '=', False)]"
    )

    code = fields.Char(
        string="Code",
        help="Code assigned for this brand must include whole parent(s) brand's code"
    )
    
    has_routes = fields.Boolean(
        string="Has routes?",
        help="Toogle to indicate that this Branch has routes",
        default=False
    )

    analytic_plan_id = fields.Many2one(
        comodel_name='account.analytic.plan',
        string="Plan",
        help="Select the Plan for this Branch",
        tracking=1,
        domain="[('parent_id', '=', False)]"
    )

    analytic_account_id = fields.Many2one(
        comodel_name='account.analytic.account',
        string="Analytic",
        help="Anaytic account that identifies this branch in Budget",
        tracking=1,
        #domain="[('company_idplan_id', '=', self.analytic_plan_id)]"
    )

    _sql_constraints = [
        ('name_uniq', 'unique (code,name)', 'The Branch name must be unique !')
    ]
