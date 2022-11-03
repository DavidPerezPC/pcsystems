


from itertools import groupby
import re
import ssl
import logging
import threading
import time
from xmlrpc.client import ServerProxy
from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _
from odoo.tools import format_datetime
from datetime import datetime, timedelta

STATUS = {
    "200": "Caja abierta satisfactoriamente.",
    "201": "Devolución hecha correctamente.",
    "500": "Ha ocurrido un error: ",
    "422": "Error en estructura de entrada, valores incorrectos: ",
    "406": "Ya se encuentra una sesión activa.",
    "407": "Orden existente: ",
    "412": "No existe sesión activa: ",
    "404": "No existe cliente con documento asignado: "
}

class PosOrder(models.Model):
    _inherit = 'pos.order'

    def NotaCredito(self, dhr, dpr, dprl):
        
        res_all = []
        env = self.env
        missing = self.validation(dhr, dpr, dprl)
        if missing != '':
            data_ident, data_tienda, data_cajafactura = "", "", ""
            if dhr['v_identidad']:
                data_ident = dhr['v_identidad']

            if dhr['v_tienda']:
                data_tienda = dhr['v_tienda']

            if dhr['v_cajafactura']:
                data_cajafactura = dhr['v_cajafactura']

            res_all.append({
                'V_IDENTIDAD': data_ident,
                'V_FECHA' : dhr['fecha'],
                'V_TIENDA': data_tienda,
                'V_CAJAFACTURA': data_cajafactura,
                'statusCode': 422,
                'error': STATUS['422'],
                'errorDetail': missing
            })
        else:
            employee_id = dhr['emp_id']
            user_id = dhr['user_id']
            config_id = dhr['config_id']
            branch_id = dhr['branch_id']
            if employee_id and user_id:
                datetime_max = dhr['v_date_max']
                datetime_min = dhr['v_date_min']
                session = dhr['session_id']
                pos_order = env['pos.order'].sudo().search([('v_caja_factura', '=', dhr['v_numero']), ('v_tienda', '=', dhr['v_tienda'])], limit=1)

                if session:
                    if pos_order: #and r['order']['V_CAJAFACTURA'] not in all_dict_with_cajas[str(r['order']['V_TIENDA'])]:
                        all_product_in_orders = [int(line.product_id.default_code) for line in pos_order.lines]
                        error = ''
                        for product in dprl:
                            product_id_val = int(product['product_id']) if type(product['product_id']) == str else product['product_id']
                            if product_id_val not in all_product_in_orders:
                                error += "Producto: {} no existe en la orden, ".format(product['product_id'])
                        if error != '':
                            error = error[:len(error) - 2]
                            res_all.append({
                                'V_IDENTIDAD': dhr['v_identidad'],
                                'V_FECHA': dhr['fecha'],
                                'V_TIENDA': dhr['v_tienda'],
                                'V_CAJAFACTURA': dhr['v_cajafactura'],
                                'statusCode': 422,
                                'error': STATUS['422'],
                                'errorDetail': error
                            })
                        else:
                            previsional_v_tienda_caja_factura = pos_order.v_tienda_caja_factura
                            pos_order.v_tienda_caja_factura = 'NC:'+pos_order.v_tienda_caja_factura
                            refund_order = pos_order.copy(pos_order.sudo()._prepare_refund_values(session))
                            pos_order.v_tienda_caja_factura = previsional_v_tienda_caja_factura
                            order_date = dhr['fecha']
                            all_date = order_date.date().strftime('%Y-%m-%d')
                            v_hora_pedido = dhr['v_hora_peedido'].replace(' ', 'T').split('T')
                            hour = v_hora_pedido[1].replace('Z', '').split('.')
                            hour = datetime.strptime(hour[0], '%H:%M:%S') + timedelta(hours=4)
                            hour = hour.strftime('%H%M%S')
                            if '000000' <= hour < '040000':
                                all_date = order_date.date()
                                all_date = all_date + timedelta(days=1)
                                all_date = all_date.strftime('%Y-%m-%d')
                            order_date = datetime.strptime("{} {}".format(all_date, hour), '%Y-%m-%d %H%M%S')
                            refund_order.sudo().write({
                                'v_igtf': 0,
                                'v_total_igtf': dhr['v_credito'] + dhr['v_efectivo'],
                                'v_tipo': 'N/C',
                                'v_caja_factura': dhr['v_cajafactura'],
                                'v_identidad': dhr['v_identidad'],
                                'v_tienda': dhr['v_tienda'],
                                'secuencia_fiscal': dhr['v_seqfiscal'],
                                'v_serialfiscal': dhr['v_seriefiscal'],
                                'cedula_empleado': dhr['v_cajeracedula'],
                                'date_order': order_date,
                                'branch_id': branch_id,
                                'case_refund': dhr['refund'],
                                'v_tienda_caja_factura': f"""{dhr['v_tienda']}/{dhr['v_cajafactura']}""",
                            })
                            amount_total, taxes_total = 0, 0
                            for line in pos_order.lines:
                                n = 0
                                for product in dprl:
                                    pos_order_line_lot = env['pos.pack.operation.lot']
                                    n += 1
                                    if line.product_id.default_code == str(product['product_id']):
                                        if product['iva'] == 0:
                                            iva = 'Exento'
                                            tax_id = env['account.tax'].sudo().search([('name', 'like', 'Exento'), ('type_tax_use', '=', 'sale')])
                                        else:
                                            iva = "{} %".format(product['iva'])
                                            tax_id = env['account.tax'].sudo().search([('name', 'like', product['iva']), ('type_tax_use', '=', 'sale')])

                                        price_subtotal_incl = (product['price'] + (product['price'] * tax_id.amount) / 100) * product['product_uom_qty']
                                        product_dict = {
                                            'name': refund_order.name,
                                            'qty': product['product_uom_qty'],
                                            'order_id': refund_order.id,
                                            'price_subtotal': product['price'] * product['product_uom_qty'],
                                            'price_subtotal_incl': price_subtotal_incl,
                                            'tax_ids': [(4, tax_id.id)] if tax_id else False,
                                            'taxes_ref': iva
                                        }
                                        amount_total += price_subtotal_incl
                                        taxes_total += abs(price_subtotal_incl) - abs(product_dict['price_subtotal'])

                                        for pack_lot in line.pack_lot_ids:
                                            pos_order_line_lot += pack_lot.copy()
                                        product_dict['pack_lot_ids'] = pos_order_line_lot
                                        line.copy(product_dict)
                                        r['product_list'].pop(n - 1)

                            payment_context = {"active_ids": refund_order.ids, "active_id": refund_order.id}
                            for m in r['order']['payment_data']:
                                method_test = env['pos.payment.method'].sudo().search([('payment_code', '=', m['code'])])
                                # Booleano para indicar si gue pagado con N/C.
                                m['nc_reference_bool'] = False
                                if 'nc_reference' in m:
                                    m['nc_reference_bool'] = True
                                else:
                                    m['nc_reference'] = 0
                                order_payment = env['pos.make.payment'].sudo().with_context(**payment_context)\
                                    .create({
                                        'amount': m['amount'],
                                        'payment_method_id': method_test.id,
                                        'banco_propio': m['bancoPropio'],
                                        'payment_date': refund_order.date_order,
                                    })
                                m['branch_id'] = branch_id.id
                                order_payment.with_context(**payment_context).check_payment(m)
                            check_paid = env['pos.order'].sudo().search([('id', '=', refund_order.id)])
                            #orders_list_create.append(check_paid['id'])
                            refund_order.amount_total, refund_order.amount_tax = amount_total, (taxes_total * -1)
                            refund_order.state, refund_order.to_invoice = 'paid', True
                            refund_order.picking_ids = refund_order.picking_ids.sudo()._create_picking_from_pos_order_lines_custom(refund_order.picking_type_id.default_location_dest_id.id, refund_order.lines, refund_order.picking_type_id)
                            refund_order.retail_processed = True
                            for payment in refund_order.payment_ids:
                                payment.payment_date = refund_order.date_order
                            for picking in refund_order.picking_ids:
                                picking.pos_session_id = refund_order.session_id.id
                                if picking.move_ids_without_package:
                                    picking.sudo().update_date_sml(picking.move_ids_without_package, picking.date, 'stock_move', branch_id)
                                    picking.sudo().change_create_date_sm(picking.move_ids_without_package, picking.date, 'stock_move')
                                picking.sudo().update_date_sml(picking.move_lines, picking.date, 'stock_move', branch_id)
                                picking.sudo().change_create_date_sm(picking.move_ids_without_package, picking.date, 'stock_move')
                            refund_order.action_pos_order_invoice_custom()
                            if refund_order.v_tipo and refund_order.v_tipo.upper() == 'ELIMINADA':
                                refund_order.account_move.button_draft()
                                refund_order.account_move.button_cancel()
                                refund_order.account_move.reverse_cancel_move(refund_order.account_move)
                                refund_order.picking_ids.make_return_picking_process(refund_order.picking_ids)
                                for pick in refund_order.picking_ids:
                                    if pick.state not in ['draft', 'done'] and pick.state == 'assigned':
                                        pick.write({'scheduled_date': refund_order.date_order, 'date': refund_order.date_order})
                                        pick.with_context(cancel_backorder=False).sudo()._action_done_custom(refund_order.date_order)
                                        for move in pick.move_line_ids_without_package:
                                            move.write({'create_date': refund_order.date_order, 'date': refund_order.date_order})
                                refund_order.write({'state': 'cancel'})
                            self.insert_data_retail(r, env)
                            res_all.append({
                                'V_IDENTIDAD': dhr['v_identidad'],
                                'V_FECHA': dhr['fecha'],
                                'V_TIENDA': dhr['v_tienda'],
                                'V_CAJAFACTURA': dhr['v_cajafactura'],
                                'statusCode': HTTPStatus.OK,
                                'detail': STATUS['201'],
                                'error': "",
                                'errorDetail': ""
                            })
                    elif not pos_order and not dhr['v_cajafactura'] in all_dict_with_cajas[str(dhr['v_tienda'])]:
                        to_negative.append(dhr)
                    elif dhr['v_cajafactura'] in all_dict_with_cajas[str(dhr['v_tienda'])]:
                        res_all.append({
                                'V_IDENTIDAD': dhr['v_identidad'],
                                'V_FECHA': dhr['fecha'],
                                'V_TIENDA': dhr['v_tienda'],
                                'V_CAJAFACTURA': dhr['v_cajafactura'],
                                'statusCode': 407,
                                'error': STATUS['407'],
                                'errorDetail': "Caja factura: {}.".format(dhr['v_cajafactura'])
                            })
                else:
                    data_ident = dhr['v_identidad']
                    data_tienda = dhr['v_tienda']
                    data_cajafactura = dh['v_cajafactura']
                    res_all.append({
                        'V_IDENTIDAD': data_ident,
                        'V_FECHA': dhr['fecha'],
                        'V_TIENDA': data_tienda,
                        'V_CAJAFACTURA': data_cajafactura,
                        'statusCode': 412,
                        'error': STATUS['412'],
                        'errorDetail': 'Tienda: {}. Caja: {}. Cajero: {}. Fecha: {}'.format(dhr['store'], dhr['box'], dhr['v_cajeracedula'], dhr['fecha'])
                    })
            else:
                data_res = ''
                if not employee_id:
                    data_res += 'Cédula: {}, '.format(dhr['v_cajeracedula'])
                if not user_id:
                    if data_res == '':
                        data_res += 'Cédula: {}, Usuario no registrado, '.format(dhr['v_cajeracedula'])
                    else:
                        data_res += 'Usuario no registrado: , '
                data_res = data_res[:len(data_res) - 2]
                res_all.append({
                    'V_IDENTIDAD': dhr['v_identidad'],
                    'V_FECHA': dhr['fecha'], 
                    'V_TIENDA': dhr['v_tienda'],
                    'V_CAJAFACTURA': dhr['v_cajafactura'],
                    'statusCode': 422,
                    "error": STATUS['422'],
                    'errorDetail': data_res
                }) 

    def validation(dhr, dpr, dplr):
        missing = ''
        if not dhr['v_hora_pedido']:
            missing += 'Hora pedido, '
        #if "order" not in data:
        #    missing += "Orden, "
        if not dhr["ci_cliente"]:
            missing += "CI cliente, "
        if not dhr["company_id"]:
            missing += "Id de compañía, "
        if not dhr["state"]:
            missing += "Tipo, "
        if not dhr["store"]:
            missing += "Tienda, "
        if not dhr["box"]:
            missing += "Caja, "
        if not dhr["combined"]:
            missing += "Tienda-caja, "
        if not dhr["v_identidad"]:
            missing += "Identidad, "
        if not dhr["v_cajeracedula"]:
            missing += "CI Cajero, "
        if not dhr["v_cajafactura"]:
            missing += "Caja-factura, "
        if not dhr["v_tienda"]:
            missing += "Tienda, "
        if not dhr["v_tipo"]:
            missing += "Tipo-orden, "
        if not dhr["rate"]:
            missing += "Tasa, "
        if len(dpr) == 0:
            missing += "Información de pago, "
        else:
            for payment in dpr:
                if not payment["code"]:
                    missing += "Código de pago, "
                if not payment["amount"]:
                    missing += "Monto, "
                if not payment["bancoPropio"]:
                    missing += "Banco Propio, "
                if not payment["banco_c"]:
                    missing += "Banco cliente, "
                if not payment["numero"]:
                    missing += "Número tarjeta, "
                if not payment["lote"]:
                    missing += "Lote, "
                if not payment["aprobacion"]:
                    missing += "Aprobación, "

        if len(dplr) == 0:
            missing += "Información de productos, "
        else:
            for product in dplr:
                if not dplr["product_id"]:
                    missing += "Referencia interna, "
                if not dplr["product_uom_qty"]:
                    missing += "Cantidad, "
                if not dplr["price"]:
                    missing += "Precio, "
                if not dplr["iva"]:
                    missing += "I.V.A., "

        if missing != '':
            missing = missing[:len(missing) - 2]
            
        return missing
