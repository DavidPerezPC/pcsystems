# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta
from itertools import groupby
from markupsafe import Markup

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.fields import Command
from odoo.osv import expression
from odoo.tools import float_is_zero, format_amount, format_date, html_keep_url, is_html_empty
from odoo.tools.sql import create_index

from odoo.addons.payment import utils as payment_utils
import requests
from odoo.addons.docx_report_pro.controllers.controllers import ReportControllerDocx as repdocx

READONLY_FIELD_STATES = {
    state: [('readonly', True)]
    for state in {'authorized', 'contract', 'cancel'}
}

LOCKED_FIELD_STATES = {
    state: [('readonly', True)]
    for state in {'contract', 'cancel'}
}

CONTRACT_STATUS = [
    ('active', 'Active'),
    ('overdue', 'Overdue'),
    ('paid', 'Paid'),
]


class CreditRequest(models.Model):
    _name = 'farmerscredit.credit.request'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin', 'utm.mixin']
    _description = "Credit Request"
    _order = 'request_date desc, id desc'
    _check_company_auto = True

    # _sql_constraints = [
    #     ('date_request_conditional_required',
    #      "CHECK((state IN ('request', 'authorized') AND date_request IS NOT NULL) OR state NOT IN ('sale', 'done'))",
    #      "A confirmed sales order requires a confirmation date."),
    # ]

    @property
    def _rec_names_search(self):
        if self._context.get('request_show_partner_name'):
            return ['name', 'partner_id.name']
        return ['name']

    #=== FIELDS ===#

    name = fields.Char(
        string="Request Reference",
        required=True, copy=False, readonly=True,
        index='trigram',
        states={'request': [('readonly', False)]},
        default=lambda self: _('New'))
    
    company_id = fields.Many2one(
        comodel_name='res.company',
        required=True, index=True,
        default=lambda self: self.env.company)    
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Applicant",
        help="Select the Applicant for this Credit (must be a Farmer)",
        required=True, readonly=False, change_default=True, index=True,
        tracking=1,
        states=READONLY_FIELD_STATES,
        domain="[('is_farmer', '=', True), ('company_id', 'in', (False, company_id))]")   
    state = fields.Selection(
        selection=[
            ('request', "Solicitud"),
            ('authorized', "Authorized"),
            ('contract', "Contract"),
            ('cancel', "Cancelled"),
        ],
        string="Status",
        readonly=True, copy=False, index=True,
        tracking=3,
        default='request')
    applicant_order_ref = fields.Char(string="Applicant Reference", copy=False)
    commitment_date = fields.Date(
        string="Granting Date", copy=False,
        states=LOCKED_FIELD_STATES,
        help="This is the granted date promised to the Applicant."
        )
    request_date = fields.Date(
        string="Request Date",
        required=True, readonly=False, copy=False,
        states=READONLY_FIELD_STATES,
        help="Date of credit request",
        default=lambda self: fields.Date.today()
    )   

    statement_date = fields.Date(
        string="Statement Date",
        readonly=False, copy=False,
        help="Date used for Statement",
        default=lambda self: fields.Date.today()
    )   

    due_date = fields.Date(
        string="Due Date",
        help="Due date for this Credit Request",
        compute="_get_due_date",
        store=True
    )

    interest_rate = fields.Float(
        string="Interest",
        help="Regular interest rate for this credit",
        digits=(10,4)
    )

    arrears = fields.Float(
        string="Arrears",
        help="Times to multiply Interest Rate for Arrears charges",
        digits=(8,2)
    )    
    
    interest_stop_date = fields.Date(
        string="Stop at",
        help="Interest will stop running from this date, only acumulated debt with no more interest"
    )

    require_signature = fields.Boolean(
        string="Online Signature",
        compute='_compute_require_signature',
        store=True, readonly=False, precompute=True,
        states=READONLY_FIELD_STATES,
        help="Request a online signature to the applicant in order to confirm credit request automatically.")
    signature = fields.Image(
        string="Signature",
        copy=False, attachment=True, max_width=1024, max_height=1024)
    signed_by = fields.Char(
        string="Signed By", copy=False)
    signed_on = fields.Datetime(
        string="Signed On", copy=False)
    
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        ondelete="restrict",
        string="Curency",
        help="Currency for this operation",
        default=33)
    
    statement_lines = fields.One2many(
        comodel_name='farmerscredit.credit.request.statement',
        inverse_name='request_id',
        string="Credit Request Statement Lines",
        copy=False, readonly=True)

    credit_request_line = fields.One2many(
        comodel_name='farmerscredit.credit.request.line',
        inverse_name='request_id',
        string="Credit Request Lines",
        states=LOCKED_FIELD_STATES,
        copy=True, auto_join=True)
    
    ref_ids = fields.One2many(
        comodel_name = 'farmerscredit.credit.request.references',
        inverse_name = 'request_id',
        string='Commercial and Personal References',
        states=LOCKED_FIELD_STATES,
        copy=True, auto_join=True)

    commercial_ref_ids = fields.One2many(
        comodel_name = 'farmerscredit.credit.request.references',
        inverse_name = 'request_id',
        string='Commercial References',
        domain=[('is_personal', '=', False)],
        states=LOCKED_FIELD_STATES,
        copy=True, auto_join=True)

    personal_ref_ids = fields.One2many(
        comodel_name = 'farmerscredit.credit.request.references',
        inverse_name = 'request_id',
        string='Personal References',
        domain=[('is_personal', '=', True)],
        states=LOCKED_FIELD_STATES,
        copy=True, auto_join=True)        

    guarantees_ids = fields.Many2many(
        comodel_name='farmerscredit.partner.guarantees',
        relation='farmerscredit_request_guarantee_rel',
        column1='request_id',
        column2='guarantee_id',
        string="Guarantees",
        copy=False,
    )

    ministering_ids = fields.One2many(
            'farmerscredit.credit.request.ministering', 
            'request_id', 
            string='Ministering',
            help="Ministering for the Credit Request",
            copy=False,
            auto_join=True)
    
    ministering_count = fields.Integer(compute="_compute_ministering_count", store=False, readonly=True)
    lines_count = fields.Integer(compute="_compute_ministering_count", store=False, readonly=True)

    # Partner-based computes
    note = fields.Html(
        string="Terms and conditions",
        store=True, readonly=False)

    partner_endorsement_id = fields.Many2one(
        comodel_name='res.partner',
        string="Endorsement",
        help="Select the person who will be the endorsement for the applicant",
        compute='_compute_partner_endorsement_id',
        store=True, readonly=False, required=True, precompute=True,
        states=LOCKED_FIELD_STATES,
        domain="[('type', '=', 'private'), ('parent_id', '=', partner_id), \
                '|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    
    payment_term_id = fields.Many2one(
        comodel_name='account.payment.term',
        string="Payment Terms",
        compute='_compute_payment_term_id',
        store=True, readonly=False, precompute=True, check_company=True,  # Unrequired company
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")

    user_id = fields.Many2one(
        comodel_name='res.users',
        string="Salesperson",
        compute='_compute_user_id',
        store=True, readonly=False, precompute=True, index=True,
        tracking=2,
        domain=lambda self: "[('groups_id', '=', {}), ('share', '=', False), ('company_ids', '=', company_id)]".format(
            self.env.ref("sales_team.group_sale_salesman").id
        ))
    
    team_id = fields.Many2one(
        comodel_name='crm.team',
        string="Sales Team",
        compute='_compute_team_id',
        store=True, readonly=False, precompute=True, ondelete="set null",
        change_default=True, check_company=True,  # Unrequired company
        tracking=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")

    # Lines and line based computes
    amount_untaxed = fields.Monetary(string="Untaxed Amount", store=True, compute='_compute_amounts', tracking=5)
    amount_tax = fields.Monetary(string="Taxes", store=True, compute='_compute_amounts')
    amount_total = fields.Monetary(string="Total", store=True, compute='_compute_amounts', tracking=4)

    invoice_count = fields.Integer(string="Invoice Count", compute='_get_invoice_count')
    total_invoiced = fields.Monetary(string="Invoiced", compute='_compute_amounts')
    invoice_ids = fields.One2many(
        comodel_name='account.move',
        inverse_name = 'request_id',
        string="Invoices issued on behalf this Contract",
        domain="[('move_type', '=', 'out_invoice')]",
        copy=False,
        autojoin=True)
    
    payment_count = fields.Integer(string="Payment Count", compute='_get_payment_count')
    total_payments = fields.Monetary(string="Payments", compute='_compute_amounts')
    payment_ids = fields.One2many(
        comodel_name='account.payment',
        inverse_name = 'request_id',
        string="Payments done to this Contract",
        domain="[('payment_type', '=', 'inbound'), ('partner_type', '=', 'customer')]",
        copy=False,
        autojoin=True)

    transfer_count = fields.Integer(string="Invoice Count", compute='_get_transfer_count')
    total_transfers = fields.Monetary(string="Transfers", compute='_compute_amounts')
    transfer_ids = fields.One2many(
        comodel_name='account.payment',
        inverse_name = 'request_id',
        string="Transfers done to this Contract",
        domain="[('payment_type', '=', 'outbound'), ('partner_type', '=', 'customer')]",
        copy=False,
        autojoin=True)

    # Followup ?
    analytic_account_id = fields.Many2one(
        comodel_name='account.analytic.account',
        string="Analytic Account",
        copy=False, check_company=True,  # Unrequired company
        states=READONLY_FIELD_STATES,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")


    # Remaining non stored computed fields (hide/make fields readonly, ...)
    amount_undiscounted = fields.Float(
        string="Amount Before Discount",
        compute='_compute_amounts', digits=0)
    country_code = fields.Char(related='company_id.account_fiscal_country_id.code', string="Country code")
    partner_credit_warning = fields.Text(
        compute='_compute_partner_credit_warning',
        groups='account.group_account_invoice,account.group_account_readonly')
    tax_totals = fields.Binary(compute='_compute_amounts', exportable=False)
    terms_type = fields.Selection(related='company_id.terms_type')
    type_name = fields.Char(string="Type Name", compute='_compute_type_name')

    _sql_constraints = [
        ('credit_request_unique_name', "UNIQUE(name)", _('Credit Request name must be Unique')),]
    
    # Remaining ux fields (not computed, not stored)
    def init(self):
        create_index(self._cr, 'credit_request_date_order_id_idx', 'farmerscredit_credit_request', ["request_date desc", "id desc"])

    #=== COMPUTE METHODS ===#

    @api.depends('company_id')
    def _compute_require_signature(self):
        for order in self:
            order.require_signature = order.company_id.portal_confirmation_sign

    @api.depends("ministering_ids","credit_request_line")
    def _compute_ministering_count(self):
        count = 0
        for rec in self:
            rec.ministering_count = len(rec.ministering_ids)
            rec.lines_count = len(rec.credit_request_line)
            count = len(rec.ministering_ids)
        
        return count

    @api.depends("credit_request_line")
    def _get_due_date(self):
        due_date = False
        if self.credit_request_line:
            due_date = self.credit_request_line[0].season_id.date_end
        self.due_date = due_date

    @api.model
    def _get_note_url(self):
        return self.env.company.get_base_url()

    @api.depends('partner_id')
    def _compute_partner_endorsement_id(self):
        for order in self:
            order.partner_endorsement_id = order.partner_id.address_get(['private'])['private'] if order.partner_id else False
    
    @api.depends('partner_id')
    def _compute_payment_term_id(self):
        for order in self:
            order = order.with_company(order.company_id)
            order.payment_term_id = order.partner_id.property_payment_term_id

    @api.depends('partner_id')
    def _compute_user_id(self):
        for order in self:
            if not order.user_id:
                order.user_id = order.partner_id.user_id or \
                    (self.user_has_groups('sales_team.group_sale_salesman') and self.env.user)

    @api.depends('partner_id', 'user_id')
    def _compute_team_id(self):
        cached_teams = {}
        for order in self:
            default_team_id = self.env.context.get('default_team_id', False) or order.team_id.id or order.partner_id.team_id.id
            user_id = order.user_id.id
            company_id = order.company_id.id
            key = (default_team_id, user_id, company_id)
            if key not in cached_teams:
                cached_teams[key] = self.env['crm.team'].with_context(
                    default_team_id=default_team_id
                )._get_default_team_id(
                    user_id=user_id, domain=[('company_id', 'in', [company_id, False])])
            order.team_id = cached_teams[key]

    #@api.depends('invoice_ids','credit_request_line.credit_amount', 'credit_request_line.area', 'credit_request_line.quota_per_unit')
    def _compute_amounts(self):
        """Compute the total amounts of the CR."""
        for credit in self:
        #     credit_request_lines = order.credit_request_line.filtered(lambda x: not x.display_type)
        #     order.amount_untaxed = sum(credit_request_lines.mapped('price_subtotal'))
        #     order.amount_total = sum(credit_request_lines.mapped('price_total'))

            invoices = credit.invoice_ids.filtered(lambda l: l.move_type == 'out_invoice')
            payments = credit.payment_ids.filtered(lambda l: l.partner_type == 'customer' and l.payment_type == 'inbound')
            transfers = credit.transfer_ids.filtered(lambda l: l.partner_type == 'customer' and l.payment_type == 'outbound')
            has_movtos = (len(invoices) > 0 or len(payments) > 0 or len(transfers) > 0)
            if has_movtos and not credit.statement_lines:                
                credit.statement_date = fields.Date.today()
                credit.credit_request_statament()
                # statament_lines = self._get_statement_lines()
                # credit.writh({'statement_lines': (2, credit.id)})
                # credit.write({'statement_lines': (0,0, [statament_lines])})
        
            #for inv in self.invoice_ids:
            #    if inv.move_type == 'out_invoice':
            #        total += inv.amount_total
            credit.total_invoiced = sum(invoices.mapped('amount_total'))
            credit.total_payments = sum(payments.mapped('amount'))
            credit.total_transfers = sum(transfers.mapped('amount'))
            credit.amount_tax = sum(credit.statement_lines.mapped('interest'))
            credit.amount_undiscounted = sum(credit.credit_request_line.mapped('credit_amount'))
            credit.amount_untaxed = (credit.total_invoiced - credit.total_payments + credit.total_transfers) or \
                        credit.amount_undiscounted
            credit.amount_total = credit.amount_untaxed + credit.amount_tax
            credit.tax_totals = 0


    @api.depends('partner_id')
    def _compute_guarantee_ids(self):
        for record in self:
            record.guarantees_ids = record.partner_id.guarantee_ids
            
    @api.depends('company_id', 'fiscal_position_id')
    def _compute_tax_country_id(self):
        for record in self:
            if record.fiscal_position_id.foreign_vat:
                record.tax_country_id = record.fiscal_position_id.country_id
            else:
                record.tax_country_id = record.company_id.account_fiscal_country_id

    @api.depends('company_id', 'partner_id', 'amount_total')
    def _compute_partner_credit_warning(self):
        for order in self:
            order.with_company(order.company_id)
            order.partner_credit_warning = ''
            show_warning = order.state in ('draft', 'sent') and \
                           order.company_id.account_use_credit_limit
            if show_warning:
                updated_credit = order.partner_id.commercial_partner_id.credit + (order.amount_total)
                order.partner_credit_warning = self.env['account.move']._build_credit_warning_message(
                    order, updated_credit)

    @api.depends('amount_total', 'amount_untaxed')
    def _compute_tax_totals(self):
        for order in self:
            credit_request_lines = order.credit_request_line
            order.tax_totals = 0
            # order.tax_totals = self.env['account.tax']._prepare_tax_totals(
            #     [x._convert_to_tax_base_line_dict() for x in credit_request_lines],
            # )

    @api.depends('state')
    def _compute_type_name(self):
        for record in self:
            if record.state in ('request', 'authorized', 'cancel'):
                record.type_name = _("Credit Request")
            else:
                record.type_name = _("Contract")

    # portal.mixin override
    def _compute_access_url(self):
        super()._compute_access_url()
        for order in self:
            order.access_url = f'/my/creditrequest/{order.id}'

    #=== ONCHANGE METHODS ===#
    @api.onchange('fiscal_position_id')
    def _onchange_fpos_id_show_update_fpos(self):
        if self.credit_request_line and (
            not self.fiscal_position_id
            or (self.fiscal_position_id and self._origin.fiscal_position_id != self.fiscal_position_id)
        ):
            self.show_update_fpos = True

    @api.onchange('partner_id')
    def _onchange_partner_id_warning(self):
        if not self.partner_id:
            return

        partner = self.partner_id

        # If partner has no warning, check its company
        if partner.sale_warn == 'no-message' and partner.parent_id:
            partner = partner.parent_id

        if partner.sale_warn and partner.sale_warn != 'no-message':
            # Block if partner only has warning but parent company is blocked
            if partner.sale_warn != 'block' and partner.parent_id and partner.parent_id.sale_warn == 'block':
                partner = partner.parent_id

            if partner.sale_warn == 'block':
                self.partner_id = False

            return {
                'warning': {
                    'title': _("Warning for %s", partner.name),
                    'message': partner.sale_warn_msg,
                }
            }

    #=== CRUD METHODS ===#
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'company_id' in vals:
                self = self.with_company(vals['company_id'])
            if vals.get('name', _("New")) == _("New"):
                seq_date = fields.Datetime.context_timestamp(
                    self, fields.Datetime.to_datetime(vals['request_date'])
                ) if 'request_date' in vals else None
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'credit.request', sequence_date=seq_date) or _("New")

        return super().create(vals_list)

    def copy_data(self, default=None):
        if default is None:
            default = {}
        if 'credit_request_line' not in default:
            default['credit_request_line'] = [
                Command.create(line.copy_data()[0])
                for line in self.credit_request_line.filtered(lambda l: not l.is_downpayment)
            ]
        return super().copy_data(default)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_draft_or_cancel(self):
        for order in self:
            if order.state not in ('request', 'cancel'):
                raise UserError(_(
                    "You can not delete an authorized Credit Request or Contract."
                    " You must first cancel it."))

    #=== ACTION METHODS ===#

    def action_draft(self):
        orders = self.filtered(lambda s: s.state in ['cancel'])
        return orders.write({
            'state': 'request',
            'signature': False,
            'signed_by': False,
            'signed_on': False,
        })

    def write(self, vals):
        return super(CreditRequest, self).write(vals)
    
    def action_create_ministering(self):

        for rec in self:
            minist_dates = {}
            for line in rec.credit_request_line:
                if not line.season_crop_info_id:
                    si = self.env['farmerscredit.season.crop.info'].search([('crop_id', '=', line.crop_id.id), ('season_id', '=', line.season_id.id)])
                    if si:
                        si = si[0]
                        line.season_crop_info_id = si
                else:
                    si = line.season_crop_info_id
                if len(minist_dates) == 0:
                    minist_dates.update({si.ministering1_date.strftime('%Y-%m-%d'): si.ministering1_amount * line.area,
                                         si.ministering2_date.strftime('%Y-%m-%d'): si.ministering2_amount * line.area,
                                         si.ministering3_date.strftime('%Y-%m-%d'): si.ministering3_amount * line.area,
                                        })
                else:
                    minist_dates[si.ministering1_date.strftime('%Y-%m-%d')] += si.ministering1_amount * line.area
                    minist_dates[si.ministering2_date.strftime('%Y-%m-%d')] += si.ministering2_amount * line.area
                    minist_dates[si.ministering3_date.strftime('%Y-%m-%d')] += si.ministering3_amount * line.area
            ministerings = []
            for minist in minist_dates:
                idminist = self.env['farmerscredit.credit.request.ministering'].create(                
                                          {'request_id': rec.id,
                                          'date_ministering': minist,
                                          'credit_granted': minist_dates[minist]
                                          })
                
            #rec.write({'ministering_ids':  ministerings})


    def action_confirm(self):
        """ Confirm the given quotation(s) and set their confirmation date.

        If the corresponding setting is enabled, also locks the Sale Order.

        :return: True
        :rtype: bool
        :raise: UserError if trying to confirm locked or cancelled SO's
        """
        if self._get_forbidden_state_confirm() & set(self.mapped('state')):
            raise UserError(_(
                "It is not allowed to confirm an order in the following states: %s",
                ", ".join(self._get_forbidden_state_confirm()),
            ))

        self.credit_request_line._validate_analytic_distribution()

        for order in self:
            if order.partner_id in order.message_partner_ids:
                continue
            order.message_subscribe([order.partner_id.id])

        self.write(self._prepare_confirmation_values())

        # Context key 'default_name' is sometimes propagated up to here.
        # We don't need it and it creates issues in the creation of linked records.
        context = self._context.copy()
        context.pop('default_name', None)

        self.with_context(context)._action_confirm()
        if self.env.user.has_group('sale.group_auto_done_setting'):
            self.action_done()

        return True

    def _get_forbidden_state_confirm(self):
        return {'authorized', 'contract', 'cancel'}

    def _prepare_confirmation_values(self):
        """ Prepare the Credit Request confirmation values.

        Note: self can contain multiple records.

        :return: Sales Order confirmation values
        :rtype: dict
        """
        return {
            'state': 'authorized',
            #'commitment_date': fields.Datetime.now()
        }

    def _action_confirm(self):
        """ Implementation of additional mechanism of Sales Order confirmation.
            This method should be extended when the confirmation should generated
            other documents. In this method, the SO are in 'sale' state (not yet 'done').
        """
        # create an analytic account if at least an expense product
        for order in self:
            if any(expense_policy not in [False, 'no'] for expense_policy in order.credit_request_line.product_id.mapped('expense_policy')):
                if not order.analytic_account_id:
                    order._create_analytic_account()

    def _send_order_confirmation_mail(self):
        if not self:
            return

        if self.env.su:
            # sending mail in sudo was meant for it being sent from superuser
            self = self.with_user(SUPERUSER_ID)

        for sale_order in self:
            mail_template = sale_order._get_confirmation_template()
            if not mail_template:
                continue
            sale_order.with_context(force_send=True).message_post_with_template(
                mail_template.id,
                composition_mode='comment',
                email_layout_xmlid='mail.mail_notification_layout_with_responsible_signature',
            )

    def action_done(self):
        for order in self:
            tx = order.sudo().transaction_ids._get_last()
            if tx and tx.state == 'pending' and tx.provider_id.code == 'custom':
                tx._set_done()
                tx.write({'is_post_processed': True})
        self.write({'state': 'done'})

    def action_unlock(self):
        self.write({'state': 'sale'})

    def action_cancel(self):
        """ Cancel SO after showing the cancel wizard when needed. (cfr :meth:`_show_cancel_wizard`)

        For post-cancel operations, please only override :meth:`_action_cancel`.

        note: self.ensure_one() if the wizard is shown.
        """
        cancel_warning = self._show_cancel_wizard()
        if cancel_warning:
            self.ensure_one()
            template_id = self.env['ir.model.data']._xmlid_to_res_id(
                'sale.mail_template_sale_cancellation', raise_if_not_found=False
            )
            lang = self.env.context.get('lang')
            template = self.env['mail.template'].browse(template_id)
            if template.lang:
                lang = template._render_lang(self.ids)[self.id]
            ctx = {
                'default_use_template': bool(template_id),
                'default_template_id': template_id,
                'default_order_id': self.id,
                'mark_so_as_canceled': True,
                'default_email_layout_xmlid': "mail.mail_notification_layout_with_responsible_signature",
                'model_description': self.with_context(lang=lang).type_name,
            }
            return {
                'name': _('Cancel %s', self.type_name),
                'view_mode': 'form',
                'res_model': 'sale.order.cancel',
                'view_id': self.env.ref('sale.sale_order_cancel_view_form').id,
                'type': 'ir.actions.act_window',
                'context': ctx,
                'target': 'new'
            }
        else:
            return self._action_cancel()

    def _action_cancel(self):
        inv = self.invoice_ids.filtered(lambda inv: inv.state == 'draft')
        inv.button_cancel()
        return self.write({'state': 'cancel'})

    def _show_cancel_wizard(self):
        """ Decide whether the sale.order.cancel wizard should be shown to cancel specified orders.

        :return: True if there is any non-draft order in the given orders
        :rtype: bool
        """
        if self.env.context.get('disable_cancel_warning'):
            return False
        return any(so.state != 'draft' for so in self)

    def action_preview_sale_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'target': 'self',
            'url': self.get_portal_url(),
        }

    def action_update_taxes(self):
        self.ensure_one()

        lines_to_recompute = self.credit_request_line
        lines_to_recompute._compute_tax_id()
        self.show_update_fpos = False

        if self.partner_id:
            self.message_post(body=_(
                "Product taxes have been recomputed according to fiscal position %s.",
                self.fiscal_position_id._get_html_link() if self.fiscal_position_id else "",
            ))

    # INVOICING #

    def _get_invoice_count(self):
        
        for record in self:
            record.invoice_count = self.env['account.move'].search_count(
                [('request_id', '=', self.id),('move_type', '=', 'out_invoice')])

    def action_view_invoice(self):
        invoices = self.mapped('invoice_ids').filtered(lambda l: l.move_type == 'out_invoice')
        action = self.env['ir.actions.actions']._for_xml_id('account.action_move_out_invoice_type')
        if len(invoices) <= 1 :
            form_view = [(self.env.ref('account.view_move_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = invoices.id
        else:
            action['domain'] = [('id', 'in', invoices.ids),('move_type', '=', 'out_invoice')]
        # if len(invoices) > 1 :
        #     action['domain'] = [('id', 'in', invoices.ids),('move_type', '=', 'out_invoice')]
        # elif len(invoices) == 1:
        #     form_view = [(self.env.ref('account.view_move_form').id, 'form')]
        #     if 'views' in action:
        #         action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
        #     else:
        #         action['views'] = form_view
        #     action['res_id'] = invoices.id
        # else:
        #     action = {'type': 'ir.actions.act_window_close'}

        context = {
            'default_move_type': 'out_invoice',
        }
        if len(self) <= 1:
            context.update({
                'default_partner_id': self.partner_id.id,
                'default_invoice_payment_term_id': self.payment_term_id.id or self.partner_id.property_payment_term_id.id or self.env['account.move'].default_get(['invoice_payment_term_id']).get('invoice_payment_term_id'),
                'default_invoice_origin': self.name,
                'default_user_id': self.user_id.id,
                'default_request_id': self.id,
                'default_invoice_date_due': self.due_date,
            })
        action['context'] = context
        return action

    def _get_invoice_grouping_keys(self):
        return ['company_id', 'partner_id']


    # MAIL #

    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        if self.env.context.get('mark_so_as_sent'):
            self.filtered(lambda o: o.state == 'draft').with_context(tracking_disable=True).write({'state': 'sent'})
        return super(SaleOrder, self.with_context(mail_post_autofollow=self.env.context.get('mail_post_autofollow', True))).message_post(**kwargs)

    def _notify_get_recipients_groups(self, msg_vals=None):
        """ Give access button to users and portal customer as portal is integrated
        in sale. Customer and portal group have probably no right to see
        the document so they don't have the access button. """
        groups = super()._notify_get_recipients_groups(msg_vals=msg_vals)
        if not self:
            return groups

        self.ensure_one()
        if self._context.get('proforma'):
            for group in [g for g in groups if g[0] in ('portal_customer', 'portal', 'follower', 'customer')]:
                group[2]['has_button_access'] = False
            return groups
        local_msg_vals = dict(msg_vals or {})

        # portal customers have full access (existence not granted, depending on partner_id)
        # try:
        #     customer_portal_group = next(group for group in groups if group[0] == 'portal_customer')
        # except StopIteration:
        #     pass
        # else:
        #     access_opt = customer_portal_group[2].setdefault('button_access', {})
        #     is_tx_pending = self.get_portal_last_transaction().state == 'pending'
        #     if self._has_to_be_signed(include_draft=True):
        #         if self._has_to_be_paid():
        #             access_opt['title'] = _("View Quotation") if is_tx_pending else _("Sign & Pay Quotation")
        #         else:
        #             access_opt['title'] = _("Accept & Sign Quotation")
        #     elif self._has_to_be_paid(include_draft=True) and not is_tx_pending:
        #         access_opt['title'] = _("Accept & Pay Quotation")
        #     elif self.state in ('draft', 'sent'):
        #         access_opt['title'] = _("View Quotation")

        # enable followers that have access through portal
        follower_group = next(group for group in groups if group[0] == 'follower')
        follower_group[2]['active'] = True
        follower_group[2]['has_button_access'] = True
        access_opt = follower_group[2].setdefault('button_access', {})
        if self.state in ('draft', 'sent'):
            access_opt['title'] = _("View Quotation")
        else:
            access_opt['title'] = _("View Order")
        access_opt['url'] = self._notify_get_action_link('view', **local_msg_vals)

        return groups

    def _notify_by_email_prepare_rendering_context(self, message, msg_vals, model_description=False,
                                                   force_email_company=False, force_email_lang=False):
        render_context = super()._notify_by_email_prepare_rendering_context(
            message, msg_vals, model_description=model_description,
            force_email_company=force_email_company, force_email_lang=force_email_lang
        )
        subtitles = [render_context['record'].name]

        subtitles.append(format_amount(self.env, self.amount_total, self.company_id.currency_id, lang_code=render_context.get('lang')))
        render_context['subtitles'] = subtitles
        return render_context

    def _sms_get_number_fields(self):
        """ No phone or mobile field is available on sale model. Instead SMS will
        fallback on partner-based computation using ``_sms_get_partner_fields``. """
        return []

    def _sms_get_partner_fields(self):
        return ['partner_id']

    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'state' in init_values and self.state == 'sale':
            return self.env.ref('sale.mt_order_confirmed')
        elif 'state' in init_values and self.state == 'sent':
            return self.env.ref('sale.mt_order_sent')
        return super()._track_subtype(init_values)

    # PAYMENT #
    def _get_payment_count(self):
        for record in self:
            record.payment_count = self._get_payment_transfer_count()

    def _get_transfer_count(self):
        for record in self:
            record.transfer_count = self._get_payment_transfer_count('outbound')

    #trabaja tanto para las trasferencias que se le hacen
    #como para los pagos que realizan los clienes
    def _get_payment_transfer_count(self, payment_type='inbound'):
        return self.env['account.payment'].search_count(
            [('request_id', '=', self.id),
             ('partner_type', '=', 'customer'),
             ('payment_type', '=', payment_type)
            ]
        )
    
    def action_view_payment(self):
        return self.action_view_payment_transfer()
    
    def action_view_transfer(self):
        return self.action_view_payment_transfer('outbound')

    def action_view_payment_transfer(self, payment_type='inbound'):

        if payment_type == 'inbound':
            msg = _('Payment done for Contract ')
            payments = self.payment_ids
        else:
            msg = _('Transfer done for Contract ')
            payments = self.transfer_ids

        msg += self.name
        payments = payments.filtered(lambda l: l.payment_type == payment_type)
        action = self.env['ir.actions.actions']._for_xml_id('account.action_account_payments')
        if len(payments) <= 1:
            form_view = [(self.env.ref('account.view_account_payment_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = payments.id
        else:
            action['domain'] = [('id', 'in', payments.ids),('payment_type', '=', payment_type)]

        context = {
            'default_partner_type': 'customer',
            'default_payment_type': payment_type
        }
        if len(self) <= 1:
            context.update({
                'default_partner_id': self.partner_id.id,
                'default_request_id': self.id,
                'default_ref': msg,
            })
        action['context'] = context

        return action

    def _force_lines_to_invoice_policy_order(self):
        for line in self.credit_request_line:
            if self.state in ['sale', 'done']:
                line.qty_to_invoice = line.product_uom_qty - line.qty_invoiced
            else:
                line.qty_to_invoice = 0

    def payment_action_capture(self):
        """ Capture all transactions linked to this sale order. """
        payment_utils.check_rights_on_recordset(self)
        # In sudo mode because we need to be able to read on provider fields.
        self.authorized_transaction_ids.sudo().action_capture()

    def payment_action_void(self):
        """ Void all transactions linked to this sale order. """
        payment_utils.check_rights_on_recordset(self)
        # In sudo mode because we need to be able to read on provider fields.
        self.authorized_transaction_ids.sudo().action_void()

    def _get_credit_request_lines_to_report(self):
        down_payment_lines = self.credit_request_line.filtered(lambda line:
            line.is_downpayment
            and not line._get_downpayment_state()
        )

        def show_line(line):
            if not line.is_downpayment:
                return True
            elif line in down_payment_lines:
                return True  # Only show posted down payments
            else:
                return False

        return self.credit_request_line.filtered(show_line)

    # PORTAL #

    def _has_to_be_signed(self, include_draft=False):
        return (self.state == 'sent' or (self.state == 'draft' and include_draft)) and not self.is_expired and self.require_signature and not self.signature

    def _get_portal_return_action(self):
        """ Return the action used to display orders when returning from customer portal. """
        self.ensure_one()
        return self.env.ref('sale.action_quotations_with_onboarding')

    def _get_report_base_filename(self):
        self.ensure_one()
        return '%s %s' % (self.type_name, self.name)

    #=== CORE METHODS OVERRIDES ===#

    @api.model
    def get_empty_list_help(self, help_msg):
        self = self.with_context(
            empty_list_help_document_name=_("sale order"),
        )
        return super().get_empty_list_help(help_msg)

    # def _compute_field_value(self, field):
    #     if field.name != 'invoice_status' or self.env.context.get('mail_activity_automation_skip'):
    #         return super()._compute_field_value(field)

    #     filtered_self = self.filtered(
    #         lambda so: so.ids
    #             and (so.user_id or so.partner_id.user_id)
    #             and so._origin.invoice_status != 'upselling')
    #     super()._compute_field_value(field)

    #     upselling_orders = filtered_self.filtered(lambda so: so.invoice_status == 'upselling')
    #     upselling_orders._create_upsell_activity()

    def name_get(self):
        if self._context.get('sale_show_partner_name'):
            res = []
            for order in self:
                name = order.name
                if order.partner_id.name:
                    name = '%s - %s' % (name, order.partner_id.name)
                res.append((order.id, name))
            return res
        return super().name_get()

    #=== BUSINESS METHODS ===#

    def _prepare_analytic_account_data(self, prefix=None):
        """ Prepare SO analytic account creation values.

        :param str prefix: The prefix of the to-be-created analytic account name
        :return: `account.analytic.account` creation values
        :rtype: dict
        """
        self.ensure_one()
        name = self.name
        if prefix:
            name = prefix + ": " + self.name
        plan = self.env['account.analytic.plan'].search([
            '|', ('company_id', '=', self.company_id.id), ('company_id', '=', False)
        ], limit=1)
        if not plan:
            plan = self.env['account.analytic.plan'].create({
                'name': 'Default',
                'company_id': self.company_id.id,
            })
        return {
            'name': name,
            'code': self.client_order_ref,
            'company_id': self.company_id.id,
            'plan_id': plan.id,
            'partner_id': self.partner_id.id,
        }

    def _create_analytic_account(self, prefix=None):
        """ Create a new analytic account for the given orders.

        :param str prefix: if specified, the account name will be '<prefix>: <so_reference>'.
            If not, the account name will be the Sales Order reference.
        :return: None
        """
        for order in self:
            analytic = self.env['account.analytic.account'].create(order._prepare_analytic_account_data(prefix))
            order.analytic_account_id = analytic

    #=== HOOKS ===#

    def add_option_to_order_with_taxcloud(self):
        self.ensure_one()

    def validate_taxes_on_sales_order(self):
        # Override for correct taxcloud computation
        # when using coupon and delivery
        return True

    #REPORTING
    def action_print_ministering(self):

        #report_obj = self.env['ir.actions.report']
        #report = report_obj.render_docx('farmerscredit.ministering_template', self.ministering_ids.ids)
        #report = report_obj._get_report_from_name('farmerscredit.ministering_template')
        #return report 
        #docids = self.ministering_ids.ids
        #docs = self.env['farmerscredit.credit.request.ministering'].browse(docids)
        #return {
        #    'doc_ids': docids,
        #    'doc_model': self.env['farmerscredit.credit.request.ministering'],
        #    'docs': docs
        #}
        # report = {
        #     'type': 'ir.actions.report',
        #     'report_name': 'farmerscredit.ministering_template',
        #     'datas': {
        #         'model': 'farmerscredit.credit.request.ministering',
        #         'ids': self.ministering_ids,
        #     },
        #     'nodestroy': True,
        # }  

        for m in self.ministering_ids:
            #url = self.env['ir.config_parameter'].get_param('web.base.url')
            #url += "/report/download"
            # report = repdocx()
            data =  f'["/report/docx/farmerscredit.ministering_template/{m.id}","docx"]'
            # context = self.env.context
            # res = report.report_download(data)
            #res = requests.post(url,json=data)
            #print(res)
            m.print_ministering(data)
             
        #return report

    def prepare_contract_report(self):
        
        data = {
            'company_representative_name': company_representative_name,
            'farmer_name': farmer_name,
            'company_public_deed_num': company_public_deed_num,
            'company_public_deed_vol': company_public_deed_vol,
            'company_public_deed_date_day': company_public_deed_date_day,
            'company_public_deed_date_month': company_public_deed_date_month,
            'company_public_deed_date_year': company_public_deed_date_year,
            'company_public_deed_notary_name': company_public_deed_notary_name,
            'company_public_deed_notary_num': company_public_deed_notary_num,
            'company_public_deed_notary_municipality': company_public_deed_notary_municipality,
            'company_public_deed_notary_state': company_public_deed_notary_state,
            'company_business_folio': company_business_folio,
            'company_business_folio_date_day': company_business_folio_date_day,
            'company_business_folio_date_month': company_business_folio_date_month,
            'company_business_folio_date_year': company_business_folio_date_year,
            'company_representative_public_deed_num': company_representative_public_deed_num,
            'company_representative_public_deed_vol': company_representative_public_deed_vol,
            'company_representative_public_deed_date_day': company_representative_public_deed_date_day,
            'company_representative_public_deed_date_month': company_representative_public_deed_date_month,
            'company_representative_public_deed_date_year': company_representative_public_deed_date_year,
            'company_representative_public_deed_notary_name': company_representative_public_deed_notary_name,
            'company_representative_public_deed_notary_num': company_representative_public_deed_notary_num,
            'company_representative_public_deed_notary_municipality': company_representative_public_deed_notary_municipality,
            'company_representative_public_deed_notary_state': company_representative_public_deed_notary_state,
            'company_representative_business_folio': company_representative_business_folio,
            'company_representative_business_folio_date_day': company_representative_business_folio_date_day,
            'company_representative_business_folio_date_month': company_representative_business_folio_date_month,
            'company_representative_business_folio_date_year': company_representative_business_folio_date_year,
            'farmer_main_activity': farmer_main_activity,
            'farmer_marital_status': farmer_marital_status,
            'farmer_total_area': farmer_total_area,
            'farmer_address_neighborhood': farmer_address_neighborhood,
            'farmer_address_municipality': farmer_address_municipality,
            'farmer_address_state': farmer_address_state,
            'farmer_contract_owner_name': farmer_contract_owner_name,
            'farmer_contract_owner_start_date_day': farmer_contract_owner_start_date_day,
            'farmer_contract_owner_start_date_month': farmer_contract_owner_start_date_month,
            'farmer_contract_owner_start_date_year': farmer_contract_owner_start_date_year,
            'farmer_contract_owner_expiration_date_day': farmer_contract_owner_expiration_date_day,
            'farmer_contract_owner_expiration_date_month': farmer_contract_owner_expiration_date_month,
            'farmer_contract_owner_expiration_date_year': farmer_contract_owner_expiration_date_year,
            'credit_amount_numbers': credit_amount_numbers,
            'credit_amount_written': credit_amount_written,
            'credit_aportacion_amount_numbers': credit_aportacion_amount_numbers,
            'credit_aportacion_amount_written': credit_aportacion_amount_written,
            'credit_total_amount_numbers': credit_total_amount_numbers,
            'credit_total_amount_written': credit_total_amount_written,
            'farmer_crop': farmer_crop,
            'farmer_crop_season': farmer_crop_season,
        }

    def prepare_statement_report(self):

        domain = [('credit','=', 0.0)]
        fields = ['date', 'move_id', 'days', 'debit:sum', 'interest:sum']
        statement_lines, detaild_lines = self._get_edc_detailed_lines()

        data = {
            'name': self.name,
            'partner_name': self.partner_id.name,
            'due_date': self.due_date,
            'statement_date': self.statement_date,
            'user_id': self.user_id.name,
            'total_debits': self.total_invoiced + self.total_transfers,
            'total_credits': self.total_payments,
            'total_interest': self.amount_tax,
            'total_balance': self.amount_total,
            'statement_lines': self.statement_lines.read(),
        }

        return data

    def _get_edc_detailed_lines(self):

        lines = self.statement_lines.read()
        acum_moves = []
        detail_moves = []
        for line in lines:
            sdate = line['date'].strftime("%x")
            try:
                index = next(i for i,di in enumerate(acum_moves) if di['date']==sdate)
            except StopIteration:
                acum_moves.append({'date': sdate, 
                                   'move_id': line['move_id'][1],
                                   'debit': line['debit'], 
                                   'interest': line['interest'],
                                   'days': line['days'],
                                   'balance': line['balance']})
                pass
            ref = line['ref'].split(",")
            if ref[0] == 'HABILITACION':
                detail_moves.append({
                    'ref': ref[1],
                    'quantity': '',
                    'product_uom_id': '', 
                    'price_unit': line['debit'],
                    'debit': line['debit'],
                    'date': line['date'] 
                })
            else:
                ref = ref[1].split("|")
                for lin in ref:
                    l = lin.split(";")
                    detail_moves.append({                   
                        'ref': l[0],
                        'quantity': l[1],
                        'product_uom_id': l[2], 
                        'price_unit': l[3],
                        'debit': l[4],
                        'date': line['date'] 
                    })
        return acum_moves, detail_moves



    #LOGIC FOR STATETMENT
    def credit_request_statament(self):

        statament_lines = self._get_statement_lines()
        self.mapped('statement_lines').unlink()
        self.write({'statement_lines': statament_lines})


    def _get_statement_lines(self):
        sql = f"""    
        SELECT aml.date, DATE '{self.statement_date}' - aml.date days, 
            aml.ref, m.name as move_name, aml.name, 
            aml.debit, aml.credit, m.id move_id,
            case when m.payment_id is not null then 
                (select concat( 'HABILITACION,', coalesce( bank_reference, 'SIN OBSERVACION' ))
                from account_payment ap 
                where ap.id = m.payment_id 
                )
			else 
                (select concat('INSUMOS,', string_agg( 
							concat( aml2."name", ';', aml2.quantity, ';', 
							uu.name->'es_MX', ';', 
							aml2.price_unit, ';', 
							aml2.price_subtotal), '|' )) 
                from account_move_line aml2
                    join uom_uom uu  on (uu.id = aml2.product_uom_id)
                where aml2.move_id = m.id and  aml2.display_type = 'product'
                group by aml2.move_id
                ) end as referencia
        FROM account_move_line aml 
            LEFT JOIN account_journal j ON (aml.journal_id = j.id)
            LEFT JOIN account_account acc ON (aml.account_id = acc.id) 
            LEFT JOIN res_currency c ON (aml.currency_id=c.id)
            LEFT JOIN account_move m ON (m.id=aml.move_id)
        WHERE m.request_id = {self.id}
            AND aml.date <= '{self.statement_date}'
            AND m.state IN ('posted')
            AND aml.account_id IN (3,4) 
            AND (((((aml.journal_id in (1, 2, 3, 4, 6, 7, 8, 9)) 
                AND (aml.parent_state = 'posted')) 
                AND (aml.company_id in (1))) 
                AND ((aml.display_type not in ('line_section', 'line_note')) OR aml.display_type IS NULL)) 
                AND ((aml.parent_state != 'cancel') OR aml.parent_state IS NULL)) 
                AND (aml.company_id IS NULL  OR (aml.company_id in (1))) 
                AND aml.full_reconcile_id IS NULL 
        ORDER BY aml.date, aml.id;"""

        self.env.cr.execute(sql)
        statement = self.env.cr.dictfetchall()
        statement_lines = []
        ini_balance = 0.0
        for line in statement:
            ini_balance += line['debit'] or 0.0
            ini_balance -= line['credit'] or 0.0
            interest = 0
            if line['debit'] > 0.0:
                interest = ((self.interest_rate / 365) * line['days']) * line['debit']
                ini_balance += interest
            statement_lines.append(
                [0, 0,
                 {
                    'date': line['date'],
                    'debit': line['debit'] or 0.0,
                    'credit': line['credit'] or 0.0,
                    'days': line['days'],
                    'move_id': line['move_id'],
                    'ref': line['referencia'],
                    'interest': interest,
                    'balance': ini_balance
                 }
                ])

        return statement_lines
