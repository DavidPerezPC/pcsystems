# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
            
class CustomerSuppliersPaymentsWizard(models.TransientModel):
    _name = 'customers.suppliers.payments.wizard'
    _description = 'Customers/Suppliers Payments Wizard'

    payment_from = fields.Date(
        string='Payment From', 
        help="Initial date for payment search", 
        required=True, default=fields.Date.context_today)
    payment_to = fields.Date(
        string='Payment To', 
        help="Final date for payment search", 
        required=True, default=fields.Date.context_today)

    def action_create_customers_suppliers_payments_wizard(self):

        """Action to fetch and display customer/supplier payments."""
        if not self.payment_from or not self.payment_to:
            return {
                'type': 'ir.actions.act_window_message',
                'title': 'No Date Provided',
                'message': 'Please select a payment date.',
            }
        payments_obj = self.env['customers.suppliers.payments']
        payments_obj.get_all_reconciled_payments(self.payment_from, self.payment_to)

        return True
        # return {
        #     'type': 'ir.actions.act_window',
        #     'name': 'Supplier Payments',
        #     'res_model': 'bekook.suppliers.payments',
        #     'view_mode': 'tree,form',
        #     'target': 'new',
        # }
    
