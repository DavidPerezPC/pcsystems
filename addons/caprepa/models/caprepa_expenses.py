# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
from random import randint


class CaprepaExpenses(models.Model):
    _name = 'caprepa.expenses'
    _description = 'Expenses Concepts'
    _order = 'code, id'

    name = fields.Char(
        string='Name',
        help='Expense Name',
        required=True)

    code = fields.Char(
        string="Sequence",
        help="Code sequence for Expense arrangement"
    )

    default_code = fields.Char(
        string='Code',
        help='Code for this expense',
        )

    category_id = fields.Many2one(
        comodel_name='product.category',
        string="Category",
    )

    product_id = fields.Many2one(
        comodel_name='product.template',
        string="Product",
    )

    account_id = fields.Many2one(
        comodel_name='account.account',
        string="Account",
        help="Account for this expense"
    )    


    def action_create_category_product(self):

        category_obj = self.env['product.category']
        product_obj = self.env['product.template']
        account_obj = self.env['account.account']
        categoryid = False
        productid = False
        company = self.env.company
        for rec in self:
            if not rec.default_code:
                category = category_obj.search([('name', '=', rec.name)])
                if category:
                    categoryid = category[0]
                else:
                    categoryid = category_obj.create({'name': rec.name})

                rec.category_id = categoryid.id 
            else:

                account = account_obj.search([('name', '=', rec.name),
                                                ('company_id', '=', company.id)
                                            ])
                product = product_obj.search([('default_code', '=', rec.default_code)])
                if product:
                    productid = product[0]
                    if account and not rec.account_id:
                        rec.account_id = account[0].id
                else:
                    data = {
                        'name': rec.name,
                        'default_code': rec.default_code,
                        'detailed_type': 'service',
                        'categ_id': categoryid.id,
                         }
                    
                    if account:
                        data.update({'property_account_expense_id': account[0].id})
                        rec.account_id = account[0].id

                    productid = product_obj.create(data)

                rec.category_id = categoryid.id 
                rec.product_id = productid.id 


    def action_create_budgets(self, byroute=False):

        company = self.env.company 

        branchobj = self.env['res.branch']
        branches =  branchobj.search([('company_id','=', company.id)])
        bb = self.env['budget.budget']

        for expense in self:
            if not expense.account_id:
                continue                 
            bpid = self._get_budgetary_position(expense, company.id)

        bps = self.env['account.budget.post'].search([('company_id', '=', company.id)])
        date_from = '2023-08-01'
        date_to = '2023-08-31'

        for branch in branches:
            print(f"Brach: {branch['code']} {branch['name']}")
            blines = []
            for analytic_acc in branch.analytic_account_ids:
                if byroute:
                    blines = []
                for bp in bps:
                    blines.append([0, 0, 
                                {
                                    'general_budget_id': bp.id,
                                    'analytic_account_id': analytic_acc.id,
                                    'date_from': date_from,
                                    'date_to': date_to,
                                    'planned_amount': 1,
                                    'company_id': company.id
                                }])
                if byroute:
                    budget = {
                        'name': f"Budget of {branch.name} in {analytic_acc.name}",
                        'date_from': date_from,
                        'date_to': date_to,
                        'budget_line': blines
                    }
                    bid = bb.sudo().create(budget)

            if not byroute:
                budget = {
                    'name': f"Budget of {branch.name}",
                    'date_from': date_from,
                    'date_to': date_to,
                    'budget_line': blines
                }
                bid = bb.sudo().create(budget)


        return True
    
    def action_create_budgets_byroute(self):
        return self.action_create_budgets(True)

    def _get_budgetary_position(self, expense, company):

        bpobj = self.env['account.budget.post']
        name = expense.name
        bp = bpobj.search([('name', '=', name),
                           ('company_id', '=', company)
                           ])
        if bp:
            bp = bp[0]
        else:
            bp = bpobj.sudo().create(
                {
                    'name': name,
                    'account_ids':  [(4,expense.account_id.id)],
                }
            )

        return bp