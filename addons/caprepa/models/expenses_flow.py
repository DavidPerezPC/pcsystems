# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime, time
from dateutil.relativedelta import relativedelta

from markupsafe import escape, Markup
from pytz import timezone, UTC
from werkzeug.urls import url_encode

from odoo import api, fields, models, _
from odoo.osv import expression
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, format_amount, format_date, formatLang, get_lang, groupby
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.exceptions import UserError, ValidationError


class ExpensesFlow(models.Model):
    _name = "caprepa.expenses.flow"
    _inherit = ['analytic.mixin','portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = "Expenses Flow"
    _rec_names_search = ['name', 'expense_ref']
    _order = 'id desc'

    def _get_branch_domain(self):
        """methode to get branch domain"""
        company = self.env.company
        branch_ids = self.env.user.branch_ids
        branch = branch_ids.filtered(
            lambda branch: branch.company_id == company)
        return [('id', 'in', branch.ids)]

   
    #@api.onchange('branch_id')
    #def _compute_analytic_ids(self):
    #    domain = [('analytic_account_id', 'in', self.branch_id.analytic_account_ids.ids)]
    #    return {'domain': {'analytic_ids': domain}}

    name = fields.Char(
        string='Name',
        help='Enter the expense description')

    date = fields.Date(
        string='Date',
        default=fields.Date.context_today,
        help='Date to register for this expense')
    
    branch_id = fields.Many2one(
        comodel_name = 'res.branch', 
        string='Branch', store=True,
        domain=_get_branch_domain,
        default=lambda self: self.env.user.branch_id.id,
        help='Select the branch that is requesting this Expense')

    #analytic_ids = fields.One2many(related='branch_id.analytic_account_ids')

    analytic_account_id = fields.Many2one(
        comodel_name='account.analytic.account', 
        string='Analytic Account',
        #compute='_compute_analytic_ids',
        help="Analytic Account that will be charged for this expense")

    employee_id = fields.Many2one(
        comodel_name='hr.employee', 
        string='Employee',
        help='Employee that triggers this Expense')
    
    department_id = fields.Many2one(
        comodel_name='hr.department', 
        string='Department',
        help="Employee's Departament",
        related='employee_id.department_id',
        store=True, readonly=True
    )

    number = fields.Char(
        string='Number',
        help='Number for this expense',
        readonly=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('validated', 'Valid'),
        ('to approve', 'To Approve'),
        ('approved', 'Approved'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled')
        ], 
        string='Status', readonly=True, index=True, copy=False, default='draft', tracking=True
        )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )

    invoice_ids = fields.One2many(
        'account.move', 
        'expense_flow_id', 
        string="Invoices",
        domain="[('move_type','in', ['in_invoice','in_receipt']), ('state', '=', 'draft')]",
        help="Invoices to cover for this Expense"
    )

    def action_validate_expense(self):
        self.ensure_one()
        for inv in self.invoice_ids:
            for line in inv.lines:
                line.analytic_distribution = self.analy
        self.state = 'to approve'

    def action_expense_approved(self):
        self.state = 'approved'
            
    def action_reset_to_draft(self):
        self.ensure_one()
        self.state = 'draft'

    def unlink(self):

        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Expense must be in Draft state to delete it'))
        return super(ExpensesFlow, self).unlink()
    
    @api.model
    def create(self, vals):    
        vals['number'] = self.env['ir.sequence'].next_by_code('caprepa_expenses_flow_code')    
        return super(ExpensesFlow, self).create(vals)
    


class IrSequence(models.Model):
    _inherit = "ir.sequence"

    @api.model
    def next_by_code(self, sequence_code, sequence_date=None):
        """ Draw an interpolated string using a sequence with the requested code.
            If several sequences with the correct code are available to the user
            (multi-company cases), the one from the user's current company will
            be used.
        """
        self.check_access_rights('read')
        seq_ids = self.search([('code', '=', sequence_code)])
        if not seq_ids:
            _logger.debug("No ir.sequence has been found for code '%s'. Please make sure a sequence is set for current company." % sequence_code)
            return False
        seq_id = seq_ids[0]
        return seq_id._next(sequence_date=sequence_date)