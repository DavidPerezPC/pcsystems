# See LICENSE file for full copyright and licensing details.
# -*- coding: utf-8 -*-
from itertools import groupby
#from msilib.schema import Error
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
#import numpy as np

EPSILON = 0.9

_logger = logging.getLogger(__name__)

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


def _log_logging(env, message, function_name, path):
    env['ir.logging'].sudo().create({
        'name': 'MySync',
        'type': 'server',
        'level': 'INFO',
        'dbname': env.cr.dbname,
        'message': message,
        'func': function_name,
        'path': path,
        'line': '0',
    })

class RPCProxyOne(object):

    rpc = None
    uid = None

    def __init__(self, server):
        """Class to store one RPC proxy server."""
        self.server = server
        #context = ssl.SSLContext()
        sublocal_url = ""
        if server.server_port:
            sublocal_url = "http://{}:{}/xmlrpc/".format(
                server.server_url,
                server.server_port,
            )
        else:
            sublocal_url = "http://{}/xmlrpc/".format(
                server.server_url
            )
        local_url = sublocal_url + "common"
        #rpc = ServerProxy(local_url, context=context)
        rpc = ServerProxy(local_url)
        self.uid = rpc.login(server.server_db, server.login, server.password)
        local_url = sublocal_url + "object"
        # local_url = "http://%s:%d/xmlrpc/object" % (
        #     server.server_url,
        #     server.server_port,
        # )
        #self.rpc = ServerProxy(local_url, context=context)
        self.rpc = ServerProxy(local_url)

    def __getattr__(self, name):
        return lambda *args, **kwargs: self.rpc.execute(
            self.server.server_db,
            self.uid,
            self.server.password,
            self.ressource,
            name,
            *args
        )

class RPCProxy(object):
    """Class to store RPC proxy server."""
    
    def __init__(self, server):
        self.server = server

    def get(self):
        return RPCProxyOne(self.server)

class BaseSynchro(models.TransientModel):
    """Base Synchronization."""

    _name = "plansuarez.synchro"
    _description = "Plan Suarez Synchronization"

    @api.depends("target_server")
    def _compute_report_vals(self):
        self.report_total = 0
        self.report_create = 0
        self.report_write = 0

    server_url = fields.Many2one(
        "plansuarez.synchro.server", "Source Server", 
        required=True, 
        domain=[('connection_type', '=', 'psql')]
    )
    target_server = fields.Many2one( 
        "plansuarez.synchro.server", "Target Server", 
        required=True,
        domain=[('connection_type', '=', 'odoo')]
        )
    
    action = fields.Selection(
        [("s", "Sales"), ("i", "Inventory"), ("b", "Both")],
        string="Type",
        help="What would be created: Sales=Only Sales, I=Only Inventory, B=Sales & Inventory",
        required=True,
        default="s",
    )

    user_id = fields.Many2one(
        "res.users", "Send Result To", default=lambda self: self.env.user
    )
    report_total = fields.Integer(compute="_compute_report_vals")
    report_create = fields.Integer(compute="_compute_report_vals")
    report_write = fields.Integer(compute="_compute_report_vals")

    

    @api.model
    def synchronize(self, server, target):

        sync_start_at = fields.Datetime.now()
        report_total = 0
        report_create = 0
        pool1 = RPCProxy(target)
        tgt_rpc = pool1.get().rpc
        tgt_uid = pool1.get().uid
        tgt_db = pool1.server.server_db
        tgt_pwd = pool1.server.password

        sql = """
            select id, "name" from account_tax at
            where at."name" like 'Exento%' and at.type_tax_use = 'sale';
        """
        tax_exento = self.server_url.getdata(sql, True)[0] 
        sql = """
            select dhr.id
            from data_header_retail dhr 
                join pos_order po on (po.v_tienda = dhr.v_tienda and po.v_caja_factura = dhr.v_cajafactura)
            where (dhr."valid" is not null or dhr."valid" = False) and dhr.pos_order_id != null; 
        """       
        tgt_info = {
            'tgt_rpc': tgt_rpc,
            'tgt_uid': tgt_uid,
            'tgt_db': tgt_db,
            'tgt_pwd': tgt_pwd,
        }

        po_data = {
            'dhrs': self.get_po_valid(),
            'dprs': [],
            'dplrs': [], 
            'po_created': [],
            'ncs': [],
            'eliminadas': [],
            'errors': [],
            'duplicadas': self.server_url.getdata(sql),
            'tax_exento': tax_exento
        }


        # domain = [[ ['id', '=', 875920  ] ]]
        # picking_ids = tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'pos.order', 'search_read', domain, 
        #                                         {'fields': ['id', 'name', 'picking_ids', 'session_id']})
        # picking_ids = picking_ids[0]['picking_ids']
        # for pick in picking_ids:
        #     domain = [[ ['id', '=', pick] ]]
        #     picking = tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'stock.picking', 'search_read', domain, 
        #                                         {'fields': ['id', 'name', 'location_dest_id', 
        #                                            'move_ids_without_package', 'move_lines', 'date', 'branch_id']})
        self.create_pos_orders(tgt_info, po_data)

        if len(po_data['ncs']) > 0:
            self.create_credits(tgt_info, po_data)

        endtime = fields.Datetime.now()
        syncro = {
            'name': "Sincronización del {} al {}".format(datetime.strftime(sync_start_at, '%Y-%m-%d %H:%M:%S'), datetime.strftime(endtime, '%Y-%m-%d %H:%M:%S')),
            'domain': "[('valid', '=', False), ('pos_order_id', '=' False)]",
            'server_id': self.target_server.id,
            'synchronize_date': sync_start_at,
            'synchronize_end': endtime,
            'action': self.action,
            'line_id': self.errors
        }
        self.env['plansuarez.synchro.obj'].create(syncro)

        print("Total procesados: {}".format(report_total))

        return True


    def create_pos_orders(self, tgt_info, po_data, negative=False):

        tgt_rpc = tgt_info['tgt_rpc']
        tgt_uid = tgt_info['tgt_uid']
        tgt_db = tgt_info['tgt_db']
        tgt_pwd = tgt_info['tgt_pwd']

        es_nc = False
        es_eliminada = False
        tax_exento = po_data['tax_exento']
        po_created = po_data['po_created']
        duplicadas = po_data['duplicadas']
        ncs = po_data['ncs']
        eliminadas = po_data['eliminadas']
        errors = po_data['errors']
        dhrs = po_data['dhrs']
        dprs = po_data['dprs']
        dplrs = po_data['dplrs']

        errmsg = ''
        for dhr in dhrs:
            refund = False
            self.report_total += 1
            #no proceses todavia
            print("Procesando {}-{}".format(dhr['v_tienda'], dhr['v_cajafactura']), end=". ")
            oid = [dhr['id'], dhr['v_tienda'], dhr['v_cajafactura'], dhr['config_id']]
            es_nc = dhr['v_tipo'] == 'N/C' 
            es_eliminada = dhr['v_tipo'] == 'ELIMINADA'
    
            if dhr['id'] in duplicadas:
                errmsg = "Caja factura: {}.".format(dhr['v_cajafactura'])
                errors.append(self.get_error(dhr, "407", errmsg))
                continue 
        
            if not dprs or not dplrs:
                dprs, dplrs = self.get_po_details(oid)

            if es_nc:
                ncs.append([dhr, dprs, dplrs])
                continue

            pospayments = []
            poslines = []
            totalpagos = 0
            productmissing = []

            errmsg = self.validation(dhr, dprs, dplrs)
            if  errmsg != '':
                errors.append(self.get_error(dhr, "422", errmsg))
                continue
            
            if not dhr["session_id"]:
                errmsg = 'Tienda: {}. Caja: {}. Cajero: {}. Fecha: {}'.format(dhr['v_store'], dhr['box'], dhr['v_cajeracedula'])
                errors.append(self.get_error(dhr, "412", errmsg))

            try:
                for dpr in dprs:

                    #valida los pagos
                    errmsg  = ''
                    banco_c = False
                    banco_propio = False

                    if not dpr['pay_method_id']:
                         errmsg = 'Método de pago: {} no registrado para esta sesión.'.format(dpr['payment_method_name'])

                    if not dpr['payment_method_id']:
                        errmsg += "Método de pago: Código, "

                    if dpr['validate_banco_propio'] and not dpr['banco_propio']:
                        errmsg += "Banco propio requerido, "

                    if dpr['banco_propio'] and not dpr['diariopago']:
                        errmsg += "Banco Propio no registrado {}, ".format(dpr['banco_propio'])
                    
                    if dpr['banco_propio'] and dpr['diariopago']:
                        banco_propio = dpr['id_banco_propio']
                        if not banco_propio:
                            data = {'banco_propio_name': "{} - {}".format(dpr['bcopropioname'],  dpr['banco_propio'])}
                            banco_propio = tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'banco.propio.info', 'create', [data])
                    
                    if dpr['banco_c'] and not dpr['banco_cliente_name']:
                        errmsg += "Banc Cliente no registrado {}, ".format(dpr['banco_c'])
                    elif dpr['banco_c']:
                        banco_c = dpr['banco_cliente_info_id']
                        if not banco_c:
                            data = {'banco_client_name': "{} - {}".format(dpr['banco_cliente_name'], dpr['banco_c'])}
                            banco_c = tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'banco.client.info', 'create', [data])

                    amount = dpr['amount']
                    amount_usd = dpr['amount_usd']
                    v_igtf = 0
                    if dpr['dolar_active']:
                        amount_usd = dpr['amount']
                        amount = dpr['amount'] * dpr['rate']
                        v_igtf = amount_usd * 0.03
                    totalpagos += amount

                    if not errmsg:
                        pospayments.append((0, 0, 
                        {
                            'payment_date': dhr['v_hora_pedido_time'],
                            'amount': amount,
                            'importe_usd': amount_usd,
                            'v_igtf': v_igtf,
                            'payment_method_id': dpr['pay_method_id'],
                            'banco_propio': banco_propio,
                            'banco_c': banco_c,
                            'numero': dpr['numero'],
                            'lote': dpr['lote'],
                            'branch_id': dhr['branch_id'],
                            'aprobacion': dpr['aprobacion'],
                            'nc_reference_str': dpr['nc_reference'],
                            'nc_reference_bool': True if dpr['nc_reference'] else False,
                        }))

                total_price_product = 0
                total_tax_amount = 0
                for dplr in dplrs:

                    if not dplr['product_tmpl_id']:
                        errmsg += "Producto: {} no existe, ".format(dplr['product_id'])
                        productmissing.append(dplr['product_id'])
                        continue
    
                    qty = dplr['product_uom_qty']
                    tax_unit = ((dplr['price'] * dplr['iva']) / 100)
                    total_tax_product = dplr['price'] + tax_unit

                    total_price_product += total_tax_product * qty
                    total_tax_amount += tax_unit * dplr['product_uom_qty']
    
                    if dplr['iva'] == 0:
                        iva = tax_exento['name']
                        tax_id = tax_exento
                    else:
                        sql = """
                            select id, "name" from account_tax at 
                            where "name" like '{} %' and type_tax_use = 'sale'
                        """.format(dplr['iva'])
                        tax_id = self.server_url.getdata(sql, True)
                        if tax_id:
                            tax_id = tax_id[0]

                        # product_exists.append(product_info.id)
                    poslines.append((0, 0, 
                    {
                        'full_product_name': dplr['product_name'],
                        'product_id': dplr['product_id'],
                        'price_unit': dplr['price'],
                        'qty': dplr['product_uom_qty'],
                        'tax_ids': [(4, tax_id['id'])] if tax_id else False,
                        'price_subtotal': dplr['price'] * dplr['product_uom_qty'],
                        'price_subtotal_incl': (total_tax_product * dplr['product_uom_qty']),
                        'taxes_ref': "{} %".format(dplr['iva']),
                    }))
                                
                v_igtf, v_total_igtf = 0, 0
                if dhr['v_igtf']:
                    v_igtf = dhr['v_igtf']

                if dhr['v_totaligtf']:
                    v_total_igtf = dhr['v_totaligtf']
    
                total_price_product = round(total_price_product, 2)
                totalpagos = round(totalpagos, 2)

                validation_order = total_price_product
                if v_total_igtf != 0:
                    validation_order = v_total_igtf
                else:
                    v_total_igtf = totalpagos
                validation_order = round(validation_order, 2)

                aux_var_methods = round(totalpagos - validation_order, 2)
                if (EPSILON * -1) <= aux_var_methods <= EPSILON:
                    total_price_product = totalpagos - v_igtf
                    total_price_product = validation_order = round(total_price_product, 2)

                if negative:
                    refund = dhr['refund']                     
                    v_total_igtf = totalpagos
                    if total_price_product != validation_order:
                        errmsg += "Montos inconsistentes: Total Orden: {} / Pago Recibido: {}, ".format(total_price_product, totalpagos)
                else:
                    if total_price_product != validation_order or (validation_order < 0 and not es_eliminada):
                        errmsg += "Montos inconsistentes: Total Orden: {} / Pago Recibido: {}, ".format(total_price_product, totalpagos)

                if errmsg == '' and \
                    (not es_eliminada or (es_eliminada and not dhr['v_cajafactura'] in po_created)):
                    data = {
                        'date_order': dhr['v_hora_pedido_time'],
                        'v_caja_factura': dhr['v_cajafactura'],
                        'v_identidad': dhr['v_identidad'],
                        'v_tienda': dhr['v_tienda'],
                        'user_id': dhr['user_id'],
                        'secuencia_fiscal': dhr['v_seqfiscal'],
                        'v_serialfiscal': dhr['v_serialfiscal'],
                        'cedula_empleado': dhr['v_cajeracedula'],
                        'company_id': dhr['company_id'],
                        'session_id': dhr['session_id'],
                        'partner_id': dhr['ci_cliente_id'],
                        'pos_rate': dhr['rate'],
                        'lines': poslines,
                        'payment_ids': pospayments,
                        'amount_paid': totalpagos,
                        'v_igtf': v_igtf,
                        'v_total_igtf': v_total_igtf,
                        'amount_total': total_price_product,
                        'amount_tax': total_tax_amount,
                        'amount_return': 0.0,
                        'to_invoice': True,
                        'branch_id': dhr['branch_id'],
                        'state': 'paid',
                        'case_refund': refund,
                        'v_tipo': dhr['v_tipo'],
                        'v_tienda_caja_factura': "{}/{}".format(dhr['v_tienda'], dhr['v_cajafactura']),
                    }
                    #po_id = self.tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'pos.order', 'create', [data])
                    #self.errors.append(self.get_error(dhr, "200", errmsg, po_id))
                    #po_created.append(po_id)
                    if es_eliminada and not negative:
                        eliminadas.append([dhr, dprs, dplrs])
                    #if es_nc and not negative:
                    #    ncs.append([dhr, dprs, dplrs])

                    if self.action in ['b', 'i']:
                        applied = tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'pos.order', 'new_create_order_picking', [po_id])
     
                    #self.updatedhr(po_id, dhr['id'])
                    #print("Orden: {}".format(po_id))
                    self.report_create += 1
                else:
                    errors.append(self.get_error(dhr, "422", errmsg))
                    print("Con error: {}".format(errmsg))
            except Exception as errPropio:
                errmsg = errmsg + repr(errPropio)
                errors.append(self.get_error(dhr, "500", errmsg))
                print("Con error: {}".format(errmsg))
                pass

        po_data.update(
            {   
                'ncs': ncs, 
                'eliminadas': eliminadas, 
                'errors': errors, 
                'po_created': po_created, 
                'duplicadas': duplicadas
            })

        return po_data
    
    def create_credits(self, tgt_info, po_data):

        tgt_rpc = tgt_info['tgt_rpc']
        tgt_uid = tgt_info['tgt_uid']
        tgt_db = tgt_info['tgt_db']
        tgt_pwd = tgt_info['tgt_pwd']
        errors = po_data['errors']
        tax_exento = po_data['tax_exento']

        credits = po_data['ncs']

        for credit in credits:
            dhr = credit[0]
            dprs = credit[1]
            dplrs = credit[2]

            errmsg = self.validation(dhr, dprs, dplrs)
            if  errmsg != '':
                errors.append(self.get_error(dhr, "422", errmsg))
                continue
            
            if not dhr["session_id"]:
                errmsg = 'Tienda: {}. Caja: {}. Cajero: {}. Fecha: {}'.format(dhr['v_store'], dhr['box'], dhr['v_cajeracedula'])
                errors.append(self.get_error(dhr, "412", errmsg))

            domain = [[
                        ['v_caja_factura', '=', dhr['v_numero']], 
                        ['v_tienda', '=', dhr['v_tienda']]
                        ]]
            pos_order = tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'pos.order', 'search_read', domain,
                            {'fields': ['id', 'name', 'session_id', 'v_tienda_caja_factura', 
                                        'pos_reference', 'amount_tax', 'amount_total', 'branch_id',
                                        'company_id']})
            if not pos_order:
                #validar si esta registrada para mandarla a negativa, o bien si ya esta registrada
                 continue 

            pos_order = pos_order[0]
            v_tienda_caja_factura = "NC:" + pos_order['v_tienda_caja_factura']
            
            order_to_copy = self.get_credit_dict(pos_order, dhr)
            domain = [[
                        ['order_id', '=', pos_order['id']]
            ]]
            pos_order_line = tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'pos.order.line', 'search_read', domain,
                                                {'fields': ['id', 'product_id', 'full_product_name']})

            product_list_aux = []
            refund_lines = []
            for line in pos_order_line:
                n = 0
                for dplr in dplrs:
                    n +=1
                    default_code = self.get_product_default_code(line['product_id'][0])
                    if default_code == dplr['product_id']:
                        if dplr['iva'] == 0:
                            iva = tax_exento['name']
                            tax_id = tax_exento
                        else:
                            sql = """
                                select id, "name", amount from account_tax at 
                                where "name" like '{} %' and type_tax_use = 'sale'
                            """.format(dplr['iva'])
                            tax_id = self.server_url.getdata(sql, True)
                            iva = ''
                            if tax_id:
                                tax_id = tax_id[0]
                                iva = tax_id['name']
                    
                        price_subtotal_incl = (dplr['price'] + (dplr['price'] * tax_id['amount']) / 100) * dplr['product_uom_qty']
                        product_dict = (0, 0, {
                            #'name': order_to_copy['name'],
                            'qty': dplr['product_uom_qty'],
                            #'order_id': refund_order,
                            'price_subtotal': dplr['price'] * dplr['product_uom_qty'],
                            'price_subtotal_incl': price_subtotal_incl,
                            'tax_ids': [(4, tax_id['id'])] if tax_id else False,
                            'taxes_ref': iva
                        })
                        refund_lines.append(product_dict)
                        amount_total += price_subtotal_incl
                        taxes_total += abs(price_subtotal_incl) - abs(product_dict['price_subtotal'])
                        product_list_aux.append(dplrs[n - 1])
                        dplrs.pop(n - 1)

            if refund_lines:
                order_to_copy.update({'lines': product_dict})
                refund_order = tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'pos.order', 'create', [order_to_copy])
                for dpr in dprs:
                    nc_reference_bool = True if dpr['nc_reference'] else False
                    data = {
                        'amount': dpr['amount'],
                        'payment_method_id': dpr['payment_method_id'],
                        'banco_propio': dpr['banco_propio'],
                        'payment_date': order_to_copy['date_order']
                    }
                    dpr.update(
                        {'payment_date': order_to_copy['date_order'], 
                        'branch_id': dhr['branch_id'],
                        'nc_reference_bool': nc_reference_bool,
                        'bancoPropio': dpr['banco_propio']
                        })
                    order_payment = tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'pos.make.payment', 'create', [data],
                                                 {'context': {'active_ids': [refund_order], 'active_id': refund_order}})
                    tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'pos.make.payment', 'check_payment', [[order_payment], dpr],
                                                 {'context': {'active_ids': [refund_order], 'active_id': refund_order}})

                self.create_credit_pickings(tgt_info, refund_order)


    def create_credit_pickings(self, tgt_info, refund_order):

        tgt_rpc = tgt_info['tgt_rpc']
        tgt_uid = tgt_info['tgt_uid']
        tgt_db = tgt_info['tgt_db']
        tgt_pwd = tgt_info['tgt_pwd']

        sql = """
            select po."name", sp.id stock_picking_id, po.session_id, 
                sp.picking_type_id, spt.default_location_dest_id
            from pos_order po join stock_picking sp on (sp.pos_order_id = po.id)
                join stock_picking_type spt on (spt.id = sp.picking_type_id)
            where po.id = {};
        """.format(refund_order)
        picking_ids = self.server_url.getdata(sql, True, True)
        domain = [[ ['id', '=', refund_order] ]]
        po = tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'pos.order', 'search_read', domain, 
                                         {'fields': ['id', 'name', 'lines', 'picking_ids', 'session_id' ]})[0]
        #picking_ids = picking_ids[0]['picking_ids'] if picking_ids else []
        for picking in picking_ids:
            params = [ [picking['id']], picking['default_location_dest_id'], 
                        po['lines'], picking['picking_type_id'] 
                    ]
            tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'stock.picking', 'cpf_pol_custom_xmlrp', params)

        po = tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'pos.order', 'search_read', domain, 
                                         {'fields': ['id', 'name', 'lines', 'picking_ids', 'session_id' ]})[0]
        picking_ids = po[0]['pickings_ids'] if picking_ids else []
        for picking in picking_ids:

            domain = [[ ['id', '=', picking] ]]
            picking = tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'stock.picking', 'search_read', domain, 
                                        {'fields': ['id', 'name', 'location_dest_id', 
                                            'move_ids_without_package', 'move_lines', 'date', 'branch_id']})
            for moves in picking:
                params = [ [moves['id']], 
                            moves['move_ids_without_package'], moves['date'], 
                            'stock_move', moves['branch_id']
                        ]
                params1 = [ [moves['id']], 
                            moves['move_ids_without_package'], moves['date'], 
                            'stock_move'
                        ]             

                if moves['move_ids_without_package']:
                    tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'stock.picking', 'update_date_sm', params)
                    tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'stock.picking', 'change_create_date_sm', params1)
                params[1] = moves['move_lines']
                params1[1] = moves['move_lines']
                tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'stock.picking', 'update_date_sm', params)
                tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'stock.picking', 'change_create_date_sm', params1)

        tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'pos.order', 
                            'action_pos_order_invoice_custom', [[refund_order]])

    def get_credit_dict(self, po, dhr):


        dict = {
            'name': po['name'] + _(' REFUND'),
            'session_id': dhr['session_id'],
            'date_order': dhr['v_hora_pedido_time'],
            'pos_reference': po['pos_reference'],
            'lines': False,
            'amount_tax': -po['amount_tax'],
            'amount_total': -po['amount_total'],
            'amount_paid': 0,
            'v_caja_factura': dhr['v_cajafactura'],
            'v_identidad': dhr['v_identidad'],
            'v_tienda': dhr['v_tienda'],
            'user_id': dhr['user_id'],
            'secuencia_fiscal': dhr['v_seqfiscal'],
            'v_serialfiscal': dhr['v_serialfiscal'],
            'cedula_empleado': dhr['v_cajeracedula'],
            'company_id': dhr['company_id'],
            'partner_id': dhr['ci_cliente_id'],
            'pos_rate': dhr['rate'],
            'v_igtf': 0,
            'v_total_igtf': dhr['v_credito'] + dhr['v_efectivo'],
            'branch_id': dhr['branch_id'],
            'state': 'paid',
            'to_invoice': True,
            'case_refund': dhr['refund'],
            'v_tipo': dhr['v_tipo'],
            'v_tienda_caja_factura': "{}/{}".format(dhr['v_tienda'], dhr['v_cajafactura']),
        }

        return dict

    def get_product_default_code(self, product_id):
        sql = """
            select pt.default_code 
            from product_product pp join product_template pt on (pt.id = pp.product_tmpl_id)
            where pp.id = {};
        """.format(product_id)
        product_info  = self.server_url.getdata(sql, True, True)

        return product_info[0]['default_code']

    def get_po_valid(self):
        sql = """
            with dhr as 
            (
                select dhr.*,  
                    (dhr.fecha - interval '4 hour')::date fecha_vta, 
                    (dhr.fecha - interval '4 hour')::date::text || ' ' || substring(dhr.v_hora_pedido::text from 12) hora_vta,
                    to_timestamp((dhr.fecha - interval '4 hour')::date::text || ' ' || substring(dhr.v_hora_pedido::text from 12), 'YYYY-MM-DD HH24:MI:SS') v_hora_pedido_time,
                    to_timestamp((dhr.fecha - interval '4 hour')::date::text || ' ' || '00:00:00', 'YYYY-MM-DD HH24:MI:SS') v_date_min,
                    to_timestamp((dhr.fecha - interval '4 hour')::date::text || ' ' || '23:59:59', 'YYYY-MM-DD HH24:MI:SS') v_date_max,
                    rb.id branch_id, rp.identification_id, 
                    rp.id emp_id, rp."name" emp_name, ru.id user_id, ru.login,
                    rpc.id ci_cliente_id
                from data_header_retail dhr
                        join res_company rc on (rc.id = dhr.company_id) 
                        join res_branch rb on (rb.telephone = dhr.v_tienda) 
                        join res_partner rp on (rp.identification_id = dhr.v_cajeracedula and rp.active)
                        left join res_partner rpc on (rpc.identification_id = dhr.ci_cliente and rpc.active)                
                        join res_users ru on (ru.partner_id = rp.id and ru.active)
                where 
                    dhr.v_tipo in ('N/C', 'ELIMINADA') 
                    --(dhr."valid" is null or dhr."valid" = false) and dhr.pos_order_id  is null            
            )
            select dhr.id, dhr.refund, dhr.v_efectivo, dhr.v_credito, dhr.v_puntos,
                dhr.fecha, dhr.v_hora_pedido, dhr.factura, dhr.v_numero,
                dhr.v_identidad, dhr.v_tienda, dhr.v_cajafactura, dhr.v_seqfiscal,
                dhr.v_serialfiscal, dhr.v_tipo, dhr.v_cajeracedula, 
                dhr.v_totaligtf, dhr.v_igtf, dhr.rate, dhr.ci_cliente,
                dhr.company_id, dhr.state, dhr.store, dhr."box", dhr.combined, 
                dhr."valid", dhr.pos_order_id, dhr.fecha_vta, dhr.hora_vta, 
                dhr.v_hora_pedido_time, dhr.v_date_min, dhr.v_date_max,
                dhr.branch_id, dhr.identification_id, dhr.emp_id, dhr.emp_name, dhr.ci_cliente_id,
                ps.user_id, dhr.login, 
                ps.id session_id, ps."name" session_name, ps.config_id, ps.start_at, ps.state,
                ps.store_box
            from dhr
                join pos_session ps on (ps.store_box = dhr.combined
                                and ps.state = 'opened'
                                and (ps.closed_on_retail is null or not ps.closed_on_retail)
                                and ps.user_id  = dhr.user_id
                                and ps.start_at - interval '4 hour' between dhr.v_date_min and dhr.v_date_max
                                );
        """
        dhr = self.server_url.getdata(sql, True)

        return dhr
 
    def get_po_details(self, poid, topythondict=False):
        
        idpo = poid[0]
        v_tienda = poid[1]
        v_cajafactura = poid[2]
        pos_config_id = poid[3]

        sql = """
            select dpr.code, dpr.amount, dhr.rate, dpr.banco_propio, dpr.banco_c, dpr.numero, dhr.v_igtf, 
                dpr.lote, dpr.aprobacion, dpr.nc_reference, dpr.v_tienda, dpr.v_cajafactura,	
                aj."name" DiarioPago, bpi.id id_banco_propio, bpi.id banco_propio_info_id, bpi.banco_propio_name,
                rbbc."name" banco_cliente_name, dpr.amount / dhr.rate amount_usd,
                ppm.id payment_method_id, ppm.payment_code, ppm."name" payment_method_name, ppm.validate_banco_propio, ppm.dolar_active , 
                pcppmr.pos_payment_method_id pay_method_id,
                rb."name" BcoPropioName,  
                rbbc.id banco_cliente_id,  bci.id banco_cliente_info_id
            from data_header_retail dhr
                join data_payment_retail dpr on (dpr.v_tienda  = dhr.v_tienda  and dpr.v_cajafactura = dhr.v_cajafactura)
                join pos_payment_method ppm on (ppm.payment_code = dpr.code)
                left join pos_config_pos_payment_method_rel pcppmr on 
                        (pcppmr.pos_config_id = {} and pcppmr.pos_payment_method_id = ppm.id)
                left join account_journal aj on (aj.id_banco_propio = dpr.banco_propio and aj."type" = 'bank')
                left join res_partner_bank rpb on (rpb.id = aj.bank_account_id)
                left join res_bank rb on (rb.id = rpb.bank_id)
                left join res_bank_banco_cliente rbbc on (rbbc.code = dpr.banco_c)
                left join banco_propio_info bpi on (bpi.banco_propio_name = concat(rb."name", ' - ', aj.id_banco_propio))
                left join banco_client_info bci on (bci.banco_client_name = concat(rbbc."name", ' - ', rbbc.code))            
            where dhr.id = {};
        """.format(pos_config_id, idpo)
        dpr = self.server_url.getdata(sql, True, topythondict)

        sql = """
            select dplr.product_id, dplr.product_uom_qty, dplr.price, dplr.iva,
                pp.id product_id, pp.product_tmpl_id, pt."name" product_name
            from data_header_retail dhr
                join data_product_lines_retail dplr on (dplr.v_tienda = dhr.v_tienda and dplr.v_cajafactura = dhr.v_cajafactura)
                left join product_product pp on (pp.default_code = dplr.product_id)
                left join product_template pt on (pt.id = pp.product_tmpl_id)
            where  dhr.id = {};
        """.format(idpo)
        dplr = self.server_url.getdata(sql, True, topythondict)


        return dpr, dplr

    
    def get_error(self, dhr, status, errmsg, remote_id=False):

        error = {
            'local_id': dhr['id'],
            'v_identidad': dhr['v_identidad'],
            'v_fecha': dhr['hora_vta'],
            'v_tienda': dhr['v_tienda'],
            'v_cajafactura': dhr['v_cajafactura'],
            'statuscode': status,
            'errordetail': errmsg
        }

        if remote_id:
            error.update({'remote_id': remote_id})

        return (0, 0, error)


    def validation(self, dhr, dpr, dplr):
        missing = ''
        if not dhr['v_hora_pedido']:
            missing += 'Hora pedido, '
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
        if not dhr["emp_id"]:
            missing += 'Cédula: {}, '.format(dhr['v_cajeracedula'])
        if not dhr["user_id"]:
            missing += 'Usuario no registrado, '

        if len(dpr) == 0:
            missing += "Información de pago, "
        else:
            for payment in dpr:
                if not payment["code"]:
                    missing += "Código de pago, "
                if not payment["amount"]:
                    missing += "Monto, "
                if not payment["banco_propio"] and payment['diariopago']:
                    missing += "Banco Propio, "
                if not payment["banco_c"] and (payment['diariopago'] or payment['banco_propio']):
                    missing += "Banco cliente, "
                if not payment["numero"] and payment['lote']:
                    missing += "Número tarjeta, "
                if payment["lote"] and not payment['numero']:
                    missing += "Lote, "
                if payment['numero'] and not payment["aprobacion"]:
                    missing += "Aprobación, "

        if len(dplr) == 0:
            missing += "Información de productos, "
        else:
            for product in dplr:
                if not product["product_id"]:
                    missing += "Referencia interna, "
                if not product["product_uom_qty"]:
                    missing += "Cantidad, "
                if not product["price"]:
                    missing += "Precio, "
                if product["iva"] is None:
                    missing += "I.V.A., "

        if missing != '':
            missing = missing[:len(missing) - 2]
            
        return missing

    def getsql_po(self, onlyid=True):

            fields = "dhr.id, dhr.v_tienda, dhr.v_cajafactura"
            group = "group by 1 "
            if not onlyid:
                fields = """
                    dhr.id, rb.id branch_id, dhr.v_cajeracedula, dhr.v_igtf, dhr.v_totaligtf, dhr.ci_cliente, 
                    rp.identification_id, rp.id, ru.login, rp."name",
                    dpr.id, dpr.code, dpr.amount, aj."name" DiarioPago, dpr.banco_propio, rbbc."name" BcoCliente, dpr.banco_c, dpr.numero, dpr.lote, dpr.aprobacion,
                    dplr.id, dplr.product_id, pp.default_code
                """
                group = ""
            
            sql = """
            select  {}
            from data_header_retail dhr
                left join res_company rc on (rc.id = dhr.company_id)
                left join res_branch rb on (rb.telephone = dhr.v_tienda)
                left join res_partner rp on (rp.identification_id = dhr.v_cajeracedula and rp.active)
                left join res_partner rpc on (rpc.id = dhr.ci_cliente::integer and rpc.active)
                join res_users ru on (ru.partner_id = rp.id and ru.active)
                left join data_payment_retail dpr on (dpr.v_tienda  = dhr.v_tienda  and dpr.v_cajafactura = dhr.v_cajafactura)
                left join data_product_lines_retail dplr on (dplr.v_tienda = dhr.v_tienda and dplr.v_cajafactura = dhr.v_cajafactura)
                left join product_product pp on (pp.default_code = dplr.product_id)
                join product_template pt on (pt.id = pp.product_tmpl_id)
                left join account_journal aj on (aj.id_banco_propio = dpr.banco_propio and aj."type" = 'bank')
                left join res_bank_banco_cliente rbbc on (rbbc.code = dpr.banco_c)
            where  
                dhr.v_hora_pedido is not null and dhr.fecha is not null
                and not dhr.refund 
                and (dhr.ci_cliente != '' and dhr.ci_cliente is not null)
                and (dhr.company_id is not null)
                and (dhr.state != '' and dhr.state is not null)
                and (dhr.store != 0 and dhr.store is not null)
                and (dhr."box" != 0 and dhr."box" is not null)
                and (dhr."combined" != '' and dhr."combined" is not null)
                and (dhr.v_identidad != '' and dhr.v_identidad is not null)
                and (dhr.v_cajeracedula != '' and dhr.v_cajeracedula is not null)
                and (dhr.v_cajafactura != '' and dhr.v_cajafactura is not null)
                and (dhr.v_tienda != '' and dhr.v_tienda is not null)
                and (dhr.v_tipo != '' and dhr.v_tipo is not null)
                and (dhr.rate != 0 and dhr.rate is not null)
                and (dpr.id is not null)
                and (dplr.id is not null)
                and (pp.id is not null)
                and ( ((dpr.banco_propio is not null or dpr.banco_propio != '') and aj.id is not null)
                    or ((dpr.banco_propio is null or dpr.banco_propio = '') and aj.id is null)
                    )
            {}
            order by 1;
            """.format(fields, group)

            return sql

    def upload_download(self):
        self.ensure_one()
        report = []
        start_date = fields.Datetime.now()
        timezone = self._context.get("tz", "UTC")
        start_date = format_datetime(
            self.env, start_date, timezone, dt_format=False
        )
        server = self.server_url
        target = self.target_server
        self.synchronize(server, target)
        # for obj_rec in server.obj_ids:
        #     _logger.debug("Start synchro of %s", obj_rec.name)
        #     dt = fields.Datetime.now()

        #     if obj_rec.action == "b":
        #         time.sleep(1)
        #         dt = fields.Datetime.now()
        #     obj_rec.write({"synchronize_date": dt})
        end_date = fields.Datetime.now()
        end_date = format_datetime(
            self.env, end_date, timezone, dt_format=False
        )
        # Creating res.request for summary results
        if self.user_id:
            request = self.env["plansuarez.res.request"]
            if not report:
                report.append("No exception.")
            summary = """Here is the synchronization report:

     Synchronization started: %s
     Synchronization finished: %s

     Synchronized records: %d
     Records updated: %d
     Records created: %d

     Exceptions:
        """ % (
                start_date,
                end_date,
                self.report_total,
                self.report_write,
                self.report_create,
            )
            summary += "\n".join(report)
            request.create(
                {
                    "name": "Synchronization report",
                    "act_from": self.env.user.id,
                    "date": fields.Datetime.now(),
                    "act_to": self.user_id.id,
                    "body": summary,
                }
            )
            return {}

    def upload_download_multi_thread(self):
        threaded_synchronization = threading.Thread(
            target=self.upload_download()
        )
        threaded_synchronization.run()
        # id2 = self.env.ref("upgrade_sync.view_upgrade_synchro_finish").id
        # return {
        #     "binding_view_types": "form",
        #     "view_mode": "form",
        #     "res_model": "plansuarez.synchro",
        #     "views": [(id2, "form")],
        #     "view_id": False,
        #     "type": "ir.actions.act_window",
        #     "target": "new",
        # }
