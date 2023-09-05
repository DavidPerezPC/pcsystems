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

    analytic_account_ids = fields.One2many(
        'account.analytic.account', 
        'branch_id', 
        "Analytic Accounts"
    )

    _sql_constraints = [
        ('name_uniq', 'unique (code,name)', 'The Branch name must be unique !')
    ]

class ResBranchAnalytic(models.Model):     
    _inherit = 'account.analytic.account'

    def _get_branch_domain(self):
        """methode to get branch domain"""
        company = self.env.company
        branch_ids = self.env.user.branch_ids
        branch = branch_ids.filtered(
            lambda branch: branch.company_id == company)
        return [('id', 'in', branch.ids)]

    branch_id = fields.Many2one(
        comodel_name='res.branch', 
        string='Branch', store=True,
        domain=_get_branch_domain,
        help='Leave this field empty if this analytic account is'
             ' shared between all branches')
