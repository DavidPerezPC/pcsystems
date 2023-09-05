# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
from random import randint


class CaprepaBrands(models.Model):
    _name = 'caprepa.brands'
    _description = 'Brands'
    _parent_store = True
    _rec_name = 'complete_name'
    _order = 'code asc'

    name = fields.Char(
        string='Name',
        help='Brand Name',
        required=True)

    code = fields.Char(
        string='Code',
        help='Code assigned to this Brand',
        required=True)

    description = fields.Text(
        string='Connection',
        help='Conecction information to read Incomes and Balances for this Brand')
        
    parent_id = fields.Many2one(
        'caprepa.brands',
        string="Parent Brand",
        ondelete='cascade',
        domain="[('id', '!=', id), ('company_id', 'in', [False, company_id])]",
    )
    
    parent_path = fields.Char(
        index='btree',
        unaccent=False,
    )
    
    children_ids = fields.One2many(
        'caprepa.brands',
        'parent_id',
        string="SubBrands",
    )
    
    children_count = fields.Integer(
        'SubBrands Count',
        compute='_compute_children_count',
    )
    
    complete_name = fields.Char(
        'Complete Name',
        compute='_compute_complete_name',
        recursive=True,
        store=True,
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=False, #lambda self: self.env.company,
    )

    branch_ids = fields.One2many(
        'res.branch',
        'brand_id',
        string="Branches",
    )

    branch_count = fields.Integer(
        'Brand Branches Count',
        compute='_compute_analytic_account_count',
    )

    #constraints
    _sql_constraints = [
        ('name_code_uniq', 'unique (code, name)', "Brand Name already exists !")
    ]

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for plan in self:
            if plan.parent_id:
                plan.complete_name = '%s / %s' % (plan.parent_id.complete_name, plan.name)
            else:
                plan.complete_name = plan.name

    @api.depends('branch_ids')
    def _compute_analytic_account_count(self):
        for plan in self:
            plan.branch_count = len(plan.branch_ids)

    # @api.depends('branch_ids', 'children_ids')
    # def _compute_all_analytic_account_count(self):
    #     for plan in self:
    #         plan.all_account_count = self.env['caprepa.brands'].search_count([('plan_id', "child_of", plan.id)])

    @api.depends('children_ids')
    def _compute_children_count(self):
        for plan in self:
            plan.children_count = len(plan.children_ids)

    def action_view_child_branches(self):
        result = {
            "type": "ir.actions.act_window",
            "res_model": "res.branches",
            "domain": [('brand_id', "child_of", self.id)],
            "context": {'default_brand_id': self.id},
            "name": _("Brand Branches"),
            'view_mode': 'list,form',
        }
        return result

    def action_view_children_brands(self):
        result = {
            "type": "ir.actions.act_window",
            "res_model": "caprepa.brands",
            "domain": [('parent_id', '=', self.id)],
            "context": {'default_parent_id': self.id},
            "name": _("SubBrands"),
            'view_mode': 'list,form',
        }
        return result

    def _get_default(self):
        plan = self.env['caprepa.brands'].sudo().search(
            ['|', ('company_id', '=', False), ('company_id', '=', self.env.company.id)],
            limit=1)
        if plan:
            return plan
        else:
            return self.env['caprepa.brands'].create({
                'name': 'Default',
                'company_id': self.env.company.id,
            })
        

class CaprepaStructure(models.Model):
    _name = "caprepa.structure"
    _order = "sequence asc"

    sequence = fields.Integer(
        string="Sequence for Process"
    )

    company_code = fields.Char(
        string="Company Code",
        help="Company's Code")

    company_name = fields.Char(
        string="Company",
        help="Company Name"
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=False, #lambda self: self.env.company,
    )

    brand_code = fields.Char(
        string="Brand Code",
        help="Code for this Brand/Branch/Route"
    )

    name = fields.Char(
        string="Name",
        help="Name of the Brand/Branch/Route",
    )

    is_brand = fields.Boolean(
        string="Is Brand?",
        help="Toggle to indicate that is Brand/SubBrand"
    )

    is_root = fields.Boolean(
        string="Is Root?",
        help="Togle to indicate that is Root Brand"
    )

    parent_id = fields.Many2one(
        'caprepa.structure',
        string="Parent Brand/SubBrand",
        ondelete='cascade',
        domain="[('id', '!=', id), ('company_id', 'in', [False, company_id])]",
    )

    full_code = fields.Char(
        help="Code that identifies each Brand/Branch/Route wthin a Company",
        string="Full Code",
    )

    branch_name = fields.Char(
        string="Branch Name",
        help="This branch whill hold all analytics account assigned"
    )

    branch_id = fields.Many2one(
        comodel_name="res.branch",
        string="Branch",
        help="Branch assigned"
    )

    def action_assign_parent(self):

        parent_id = False
        company_code = ''
        parent_brand = ''
        parent_code = ''
        companies = self.read_group([('is_brand', '=', True), ('is_root', '=', 'True')], 
                                    fields=['company_code', 'company_name'], 
                                    groupby=['company_code', 'company_name'],
                                    lazy=False
                                    )
        brandsobj = self.env['caprepa.structure']
        for company in companies:
            domain = [('company_code', '=', company['company_code'])]
            company_code = company['company_code']
            brands = self.filtered(lambda r: r.company_code == company_code)
            company_brand_code = ''
            companyid = self._get_company_id(company['company_name'])
            for brand in brands:
                if brand.is_root and brand.is_brand:
                    tmp_code = ''
                    company_brand_code = company_code + brand.brand_code 
                    parent_brand = company_brand_code
                    parent_brand_id = brand.id
                    parent_id = brand.id
                    real_parent = False
                    company_id = False
                elif brand.is_brand:
                    tmp_code = ''
                    parent_code = company_brand_code
                    company_brand_code = parent_brand + brand.brand_code
                    real_parent = parent_brand_id
                    parent_id = brand.id
                    company_id = companyid
                else:
                    tmp_code = company_brand_code
                    company_brand_code = tmp_code + brand.brand_code
                    real_parent = parent_id
                    company_id = companyid

                brand.full_code = company_brand_code
                brand.parent_id = real_parent
                brand.company_id = company_id
                if tmp_code:
                    company_brand_code = tmp_code 

    
        return True
    
    def action_create_brands(self):

        
        company01 = self #self.filtered(lambda r: r.company_code == '001')


        for rec in company01:

            print(f"Procesando Cuenta: {rec.full_code} {rec.name}")
            if rec.branch_name:
                branchid = self._get_branch_new(rec)           
            else:
                branchid = False

            if rec.is_root and rec.is_brand:
                brand_id, plan_id = self._create_analytic_plan(rec)
                root_brand = brand_id
                root_plan = plan_id
            elif rec.is_brand:
                brand_id, plan_id = self._create_analytic_plan(rec, root_brand, root_plan)
            else:
                account_id  = self._create_branch_account(rec, brand_id, plan_id, branchid)
        
        return True

    def _get_branch_new(self, rec):

        branchobj = self.env['res.branch']
        branch = branchobj.search([('name', '=', rec.branch_name)])
     
        if branch:
            branchid = branch[0]
        else:
            branchid = branchobj.sudo().create(
                {'name': rec.branch_name,
                 'code': rec.full_code,
                 'company_id': rec.company_id.id,
                 }
            )

        return branchid        
    
    def _create_analytic_plan(self, rec, parent=None, plan=None):
        
        cname = f"{rec.brand_code} {rec.name}"
        brandobj = self.env['caprepa.brands']
        brandid = brandobj.search([('code', '=', rec.brand_code),
                                   ('name', '=', rec.name)
                            ])
        if brandid:
            brand_id = brandid[0]
        else:
            data = {'name': rec.name,
                    'code': rec.brand_code,
                 }
            if parent is not None:
                data.update({'parent_id': parent.id,
                             'code': parent.code + rec.brand_code
                             })
                brandid = brandobj.search([('code', '=', data['code']),
                                   ('name', '=', data['name'])
                            ])
                if brandid:
                    brand_id = brandid[0]
                else:
                    brand_id = brandobj.sudo().create(data)

        if not plan:
            domain = [('name', '=', cname)]
        else:
            cname = f"{rec.full_code} {rec.name}"
            domain = [('name', '=', cname),
                      ('parent_id', '=', plan.id)
                      ]
        planobj = self.env['account.analytic.plan']
        planid = planobj.search(domain)
        if planid:
            plan_id = planid[0]
        else:
            data ={'name': cname,
                 'company_id': rec.company_id.id
                 }
            if plan:
                data.update({'parent_id': plan.id})
            plan_id = planobj.sudo().create(data)

        return brand_id, plan_id

    def _create_branch_account(self, rec, brand, plan_id, branchid):
        
        cname = rec.name
        analyticobj = self.env['account.analytic.account']
        analytic = analyticobj.search([('name', '=', cname),
                                       ('code', '=', rec.full_code)])

        if analytic:
            analyticid = analytic[0]
            if not analyticid.branch_id:
                analyticid.branch_id = branchid.id
        else:
            analyticid = analyticobj.sudo().create(
                {
                    'name': cname,
                    'code': rec.full_code,
                    'plan_id': plan_id.id,
                    'company_id': rec.company_id.id,
                    'branch_id': branchid.id
                }
            )

        return analyticid

    # def _create_branch_account(self, rec, brand, plan_id):
        
    #     cname = rec.name
    #     branchobj = self.env['res.branch']
    #     analyticobj = self.env['account.analytic.account']

    #     branch = branchobj.search([('name', '=', cname),
    #                                ('code', '=', rec.full_code)])
    #     analytic = analyticobj.search([('name', '=', cname),
    #                                    ('code', '=', rec.full_code)])

    #     if analytic:
    #         analyticid = analytic[0]
    #     else:
    #         analyticid = analyticobj.sudo().create(
    #             {
    #                 'name': cname,
    #                 'code': rec.full_code,
    #                 'plan_id': plan_id.id,
    #                 'company_id': rec.company_id.id
    #             }
    #         )

    #     if branch:
    #         branchid = branch[0]
    #         branchid.brand_id = brand.id
    #         branchid.analytic_plan_id = plan_id.id
    #         branchid.analytic_account_id = analyticid.id
    #     else:
    #         branchid = branchobj.sudo().create(
    #             {'name': rec.name,
    #              'code': rec.full_code,
    #              'brand_id': brand.id,
    #              'company_id': rec.company_id.id,
    #              'analytic_plan_id': plan_id.id,
    #              'analytic_account_id': analyticid.id,
    #              'has_routes': brand.parent_id is not False,
    #              }
    #         )
        
    #     return branchid



    def _get_company_id(self, name):
        company = self.env['res.company'].search([('name','=',name.strip())])
        return company[0].id if company else False
    
    def _get_analytic_plan(self, brand, plan_id=None):
        if not plan_id:
            codename = f"{brand.bran_code} {brand.name.strip()}" 
            analytic_plan = self.env['account.analytic.plan'].search(codename)

        return True
    
    def _get_analytic(self, brand):
        brand_code = brand.brand_code

        return True
    
    def _get_branch(self, brand):
        branch_code = brand.brand_code
        
        return True