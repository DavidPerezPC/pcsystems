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
        """Elimina registros del periodo y regenera con cálculo correcto de impuestos."""
        if not self.payment_from or not self.payment_to:
            return {
                'type': 'ir.actions.act_window_message',
                'title': 'Sin Fechas',
                'message': 'Selecciona el rango de fechas de pago.',
            }
        self.env['customers.suppliers.payments'].get_all_reconciled_payments(
            self.payment_from, self.payment_to)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Pagos Clientes/Proveedores',
            'res_model': 'customers.suppliers.payments',
            'view_mode': 'list,form',
            'domain': [
                ('payment_date', '>=', self.payment_from),
                ('payment_date', '<=', self.payment_to),
            ],
            'target': 'current',
        }
        # return {
        #     'type': 'ir.actions.act_window',
        #     'name': 'Supplier Payments',
        #     'res_model': 'bekook.suppliers.payments',
        #     'view_mode': 'tree,form',
        #     'target': 'new',
        # }
    
