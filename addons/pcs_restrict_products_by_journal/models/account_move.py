from odoo import models, api

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.onchange('product_id')
    def _onchange_product_id(self):
        # 1. Llamamos al método original para obtener el dominio base de Odoo
        res = super(AccountMoveLine, self)._onchange_product_id()
        
        # 2. Si no hay respuesta o dominio, inicializamos uno básico
        if not res:
            res = {'domain': {'product_id': [('purchase_ok', '=', True)]}}
        
        # 3. Obtenemos el dominio actual que Odoo ya calculó
        current_domain = res.get('domain', {}).get('product_id', [])

        # 4. Inyectamos nuestra restricción si el diario tiene productos permitidos
        if self.move_id.move_type == 'in_invoice' and self.move_id.journal_id.allowed_product_ids:
            # Combinamos: (Dominio de Odoo) AND (Nuestro filtro de IDs)
            allowed_ids = self.move_id.journal_id.allowed_product_ids.ids
            current_domain = ['&'] + current_domain + [('id', 'in', allowed_ids)]
            
            res['domain']['product_id'] = current_domain
            
        return res


# class AccountMove(models.Model):
#     _inherit = 'account.move'

#     def _get_product_catalog_domain(self):
#         # Obtenemos el dominio base del catálogo
#         domain = super()._get_product_catalog_domain()
#         # Si hay productos permitidos en el diario, los filtramos también aquí
#         if self.move_type == 'in_invoice' and self.journal_id.allowed_product_ids:
#             domain += [('id', 'in', self.journal_id.allowed_product_ids.ids)]
#         return domain