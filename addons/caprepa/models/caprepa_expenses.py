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


    
    