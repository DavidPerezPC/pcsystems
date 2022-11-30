# See LICENSE file for full copyright and licensing details.
# -*- coding: utf-8 -*-
# from itertools import groupby
# from msilib.schema import Error
# import re
# import ssl
import logging
import threading
# import time
from xmlrpc.client import ServerProxy
from odoo import api, fields, models
# from odoo.exceptions import ValidationError
from odoo.tools.translate import _
from odoo.tools import format_datetime
from datetime import datetime
from time import sleep
import json
import requests
# import numpy as np

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
        # context = ssl.SSLContext()
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
        # rpc = ServerProxy(local_url, context=context)
        rpc = ServerProxy(local_url, allow_none=True)
        self.uid = rpc.login(server.server_db, server.login, server.password)
        local_url = sublocal_url + "object"
        # local_url = "http://%s:%d/xmlrpc/object" % (
        #     server.server_url,
        #     server.server_port,
        # )
        # self.rpc = ServerProxy(local_url, context=context)
        self.rpc = ServerProxy(local_url, allow_none=True)

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
        domain=[('connection_type', '=', 'psql')],
        help="Server with POS operations to sync"
    )

    session_server = fields.Many2one(
        "plansuarez.synchro.server", "Session Server", 
        required=True, 
        domain=[('connection_type', '=', 'mssql')],
        help="Server with POS Sessions to sync"
    )
    target_server = fields.Many2one( 
        "plansuarez.synchro.server", "Target Server", 
        required=True,
        domain=[('connection_type', '=', 'odoo')],
        help="Odoo Target Server to affect with sync process"
        )

    date_to_process = fields.Date(
        string="Date",
        help="Select the date to process"
    )
    
    action = fields.Selection(
        [("s", "Sales"), ("i", "Inventory"), ("b", "Both"), 
         ("A", "Open Sessions"), ("C", "Close Sesesions"),
         ("E", "Delete Opened Sessions"), ("D", "Delete Closed Sessions"),
         ("O", "Delete Sale Orders")
        ],
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
        tgt_url = pool1.server.server_url
        tgt_port = pool1.server.server_port

        tgt_info = {
            'tgt_rpc': tgt_rpc,
            'tgt_uid': tgt_uid,
            'tgt_db': tgt_db,
            'tgt_pwd': tgt_pwd,
            'tgt_url': tgt_url,
            'tgt_port': tgt_port,
        }

        errors = []
        if  self.action not in ('A', 'C', 'D', 'E', 'O'):
            sql = """
                select id, "name", amount from account_tax at
                where at.type_tax_use = 'sale';
            """
            tax_exento = self.server_url.getdata(sql, True, True) 
            sql = """
                select concat(dhr.v_tienda, '/', dhr.v_cajafactura) v_tienda_cajafactura
                from data_header_retail dhr 
                    join pos_order po on (po.v_tienda = dhr.v_tienda and po.v_caja_factura = dhr.v_cajafactura)
                where (dhr."valid" is not null or dhr."valid" = False) 
                and dhr.pos_order_id is null and dhr.sincro_state = 'draft'; 
            """
            duplicadas =  self.server_url.getdata(sql)
            duplicadas = [x for x in duplicadas]
            print(duplicadas)

            po_data = {
                'dhrs': self.get_po_valid(),
                'dprs': [],
                'dplrs': [], 
                'po_created': [],
                'ncs': [],
                'ncs_negative': [],
                'eliminadas': [],
                'wrong_amount': self.get_po_wrongamount(),
                'errors': errors,
                'duplicadas': duplicadas,
                'tax_exento': tax_exento
            }
            self.create_pos_orders(tgt_info, po_data)
            if len(po_data['ncs']) > 0:
                self.create_credits(tgt_info, po_data)
        elif self.action in ('A', 'C'):
            errors = self.open_close_sessions(tgt_info, self.action)
            po_data = {'errors': errors }
        elif self.action in ('D', 'E'):
            errors = self.delete_sessions()
            po_data = {'errors': errors }
        else:
            errors = self.delete_orders()
            po_data = {'errors': errors }

        endtime = fields.Datetime.now()
        syncro = {
            'name': "Sincronización del {} al {}".format(datetime.strftime(sync_start_at, '%Y-%m-%d %H:%M:%S'), datetime.strftime(endtime, '%Y-%m-%d %H:%M:%S')),
            'domain': "[('valid', '=', False), ('pos_order_id', '=' False)]",
            'server_id': self.target_server.id,
            'synchronize_date': sync_start_at,
            'synchronize_end': endtime,
            'action': self.action,
            'line_id': po_data['errors']  # TODO: HE COMENTADO ESTO PORQUE ME HA DICHO QUE EL OBJETO plansuarez.synchro no tiene el objeto errors
        }
        self.env['plansuarez.synchro.obj'].create(syncro)

        print("Total procesados: {}".format(report_total))

        return True

    def delete_orders(self):

        sql = """
            with usincro as 
            (
                select dhr.id, po.id poid
                from data_header_retail dhr 
                    join pos_order po on (po.v_tienda_caja_factura = concat(dhr.v_tienda, '/', dhr.v_cajafactura))
                where dhr.sincro_state != 'done' or dhr.pos_order_id is null
            )
            update data_header_retail dhr set sincro_state = 'done', pos_order_id = usincro.poid 
            from usincro
            where dhr.id = usincro.id;
        """
        self.server_url.updatedata(sql)

        sql = """
            select *
            from data_header_retail dhr
            where sincro_state = 'done' and pos_order_id is not null
                and dhr.fecha::date = '{}';
        """.format(self.date_to_process)

        orders = self.server_url.getdata(sql, True)
        errors = []
        strdelete = ""
        sql = ""
        tablas = [
                {'tabla': 'ventas', 'cajafactura': 'v_cajafactura', 'tienda': 'v_tienda'},
                {'tabla': 'invent', 'cajafactura': 'i_cajafactura', 'tienda': 'i_tienda'},
                {'tabla': 'tabtc', 'cajafactura': 'cajafactura', 'tienda': 'tienda'},
                {'tabla': 'tabtd', 'cajafactura': 'cajafactura', 'tienda': 'tienda'},
                {'tabla': 'tabtrans', 'cajafactura': 'cajafactura', 'tienda': 'tienda'}
                ]

        for order in orders:
            print("Eliminando Orden {}".format(order['v_cajafactura']))
            strdelete += f"'{order['v_tienda']}/{order['v_cajafactura']}',"
            error = {
                'local_id': False,
                'v_identidad': order['v_identidad'],
                'v_fecha': order['fecha'],
                'v_tienda': order['v_tienda'],
                'v_cajafactura': order['v_cajafactura'],
                'statuscode': '200',
                'errordetail': "Orden Eliminada en Origen"
            }
            errors.append(self.get_error([],False, False, False, error))
        strdelete = strdelete[:len(strdelete)-1] 

        for tabla in tablas:
            print("Eliminando {}".format(tabla['tabla'].upper()))
            if strdelete:
                sql = f"delete from {tabla['tabla']}  where cast({tabla['tienda']} as varchar) + '/' + cast({tabla['cajafactura']} as varchar) in  ({strdelete}); \r\n"
                if sql:
                    self.session_server.updatedata(sql, True)

        sql =  """
                 truncate table data_header_retail;
                 truncate table data_payment_retail;
                 truncate table data_product_lines_retail;
               """
        self.server_url.updatedata(sql)
         
        return errors 

    def delete_sessions(self):
        status = 'A' if self.action == 'E' else 'C'
        domain = [('obj_id.action', '=', status), 
                    ('v_fecha', '=', self.date_to_process),
                    ('statuscode', 'in', ['200', '201']),
                ]
        sessions = self.env['plansuarez.synchro.obj.line'].search(domain)
        strfecha = datetime.strftime(self.date_to_process, "%d-%m-%Y")
        strdelete = ""
        errors = []
        for session in sessions:
            strdelete += f"delete from ControlCaja where status = '{status}' and fecha='{strfecha}' "
            strdelete += f"and cast(tienda as varchar) + '-' + cast(caja as varchar) = '{session.v_cajafactura}'"
            strdelete += f" and identidad = '{session.v_identidad}';"
            error = {
                'local_id': False,
                'v_identidad': session.v_identidad,
                'v_fecha': session.v_fecha,
                'v_tienda': session.v_tienda,
                'v_cajafactura': session.v_cajafactura,
                'statuscode': session.statuscode,
                'errordetail': "Sesión eliminada"
            }
            errors.append(self.get_error([],False, False, False, error))
        if strdelete:
            print(strdelete)
            self.session_server.updatedata(strdelete, True)

        return errors 


    def open_close_sessions(self, tgtinfo, status='A', dateformat="%d-%m-%Y"):

        errors = []
        strfecha = datetime.strftime(self.date_to_process, dateformat)
        try:
            sql = """
                select cast(tienda as varchar) + '-' + cast(caja as varchar) combined, status, cajero identification, 
                        convert(float, fondo) fund, tienda, identidad, 	
                        convert(varchar, abierta, 126) abierta, 
                        convert(varchar, cerrada, 126) cerrada, cant_orden,
                        convert(varchar, fecha, 126) fecha
                from ControlCaja cc
                where status = '{}' and cajero is not null and cajero != ''
                    and fecha >= '{}';
            """.format(status, strfecha)
            data_2_process = []
            docr = self.session_server.getdata(sql, True)
            for data in docr:
                data_2_process.append({
                    "combined": data.get('combined'),
                    "status": data.get('status'),
                    "identification": data.get('identification'),
                    "fund": data.get('fund'),
                    "tienda": data.get('tienda'),
                    "identidad": data.get('identidad'),
                    "abierta": data.get('abierta'),
                    "cerrada": data.get('cerrada'),
                    "fecha": data.get('fecha'),
                    "cant_orden": data.get('cant_orden'),
                })

            #print(data_2_process)
            final_data_2_process = { 'data': data_2_process, }

            url = f"http://{tgtinfo['tgt_url']}"
            if  tgtinfo['tgt_port'] > 0:
                url += f":{tgtinfo['tgt_port']}" 
            print("Abriendo/Cerrando sesiones en: {}/openPos".format(url))
            response = requests.post(f'{url}/openPos', json=final_data_2_process)
            sessions = json.loads(response.text)['result']
            strfecha = datetime.strftime(self.date_to_process,"%Y-%m-%d")
            for session in sessions:
                error = {
                    'local_id': False,
                    'v_identidad': session['identidad'],
                    'v_fecha': strfecha,
                    'v_tienda': session['tienda'],
                    'v_cajafactura': session['combined'],
                    'statuscode': str(session['statusCode']),
                    'errordetail': f"{session['error']} {session['detail']}"
                }
                errors.append(self.get_error([],False, False, False, error))

            print(response.text)
            #print(errors)

        except Exception as err:
            print(str(err))
            #sleep(10)
            #self.open_close_sessions()
        return errors

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
        wrong_amount = po_data['wrong_amount']
        wrong_amt = [x[0] for x in wrong_amount]
        ncs = po_data['ncs']
        eliminadas = po_data['eliminadas']
        errors = po_data['errors']
        dhrs = po_data['dhrs']
        dprs = po_data['dprs']
        dplrs = po_data['dplrs']

        lfilldetails = ( len(dprs) == 0 or len(dplrs) == 0 )
        errmsg = ''
        for dhr in dhrs:
            v_tienda_cajafactura = f"{dhr['v_tienda']}/{dhr['v_cajafactura']}"
            refund = False
            self.report_total += 1
            #no proceses todavia
            print("Procesando {}-{}".format(dhr['v_tienda'], dhr['v_cajafactura']), end=". ")
            oid = [dhr['id'], dhr['v_tienda'], dhr['v_cajafactura'], dhr['config_id']]
            es_nc = dhr['v_tipo'] == 'N/C' 
            es_eliminada = dhr['v_tipo'] == 'ELIMINADA'
    

            if v_tienda_cajafactura in duplicadas or v_tienda_cajafactura in po_created:
                errmsg = "Caja factura: {}.".format(dhr['v_cajafactura'])
                errors.append(self.get_error(dhr, "407", errmsg))
                continue 

            if dhr['id'] in wrong_amt:
                for wam in wrong_amount:
                    if wam[0] == dhr['id']:
                        errmsg = "Montos inconsistentes: Total Orden: {} / Pago Recibido: {}, ".format(wam[6], wam[3])
                        errors.append(self.get_error(dhr, "422", errmsg))
                continue
        
            if lfilldetails:
                dprs, dplrs = self.get_po_details(oid)

            if es_nc and not negative: #or (es_eliminada and negative):
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
                        errmsg += "Banco Cliente no registrado {}, ".format(dpr['banco_c'])
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
    
                    tax_id = list(filter(lambda x: x['amount'] == dplr['iva'], tax_exento))[0]
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
                    (not es_eliminada or (es_eliminada and not v_tienda_cajafactura in po_created)):
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
                    if es_eliminada:
                        data.update({'state': 'cancel'})
                    po_id = tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'pos.order', 'create', [data])
                    errors.append(self.get_error(dhr, "200", errmsg, po_id))
                    po_created.append(v_tienda_cajafactura)
                    #if es_eliminada and not negative:
                    #    eliminadas.append([dhr, dprs, dplrs])
                    #if es_nc and not negative:
                    #    ncs.append([dhr, dprs, dplrs])

                    if self.action in ['b', 'i']:
                        applied = tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'pos.order', 'new_create_order_picking', [po_id])
     
                    self.updatedhr(po_id, dhr['id'])
                    print("Orden: {}".format(po_id))
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
    
    def updatedhr(self, poid, dhrid):
        if poid:
            sql = """
                update data_header_retail set valid = True, sincro_state = 'done', pos_order_id = {}
                where id = {};
            """.format(poid, dhrid)
        else:
            sql = """
                update data_header_retail set valid = False, sincro_state = 'error'
                where id = {};
            """.format(dhrid)

        res = self.server_url.updatedata(sql)

        return res

    def create_credits(self, tgt_info, po_data):

        tgt_rpc = tgt_info['tgt_rpc']
        tgt_uid = tgt_info['tgt_uid']
        tgt_db = tgt_info['tgt_db']
        tgt_pwd = tgt_info['tgt_pwd']
        errors = po_data['errors']
        ncs_negative = po_data['ncs_negative']
        tax_exento = po_data['tax_exento']

        credits = po_data['ncs']

        for credit in credits:
            try:
                dhr = credit[0]
                dprs = credit[1]
                dplrs = credit[2]

                errmsg = self.validation(dhr, dprs, dplrs)
                if  errmsg != '':
                    errors.append(self.get_error(dhr, "422", errmsg))
                    continue
                
                if not dhr["session_id"]:
                    errmsg = 'Tienda: {}. Caja: {}. Cajero: {}. Fecha: {}'.format(dhr['v_store'], dhr['box'], dhr['v_cajeracedula'], dhr['v_hora_pedido_time'])
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
                    ncs_negative.append([dhr, dprs, dplrs])
                    continue 

                pos_order = pos_order[0]
                # v_tienda_caja_factura = "NC:" + pos_order['v_tienda_caja_factura']
                
                order_to_copy = self.get_credit_dict(pos_order, dhr)
                domain = [[
                            ['order_id', '=', pos_order['id']]
                ]]
                pos_order_line = tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'pos.order.line', 'search_read', domain,
                                                    {'fields': ['id', 'product_id', 'full_product_name']})

                # product_list_aux = []
                refund_lines, amount_total, taxes_total = [], 0, 0
                for line in pos_order_line:
                    if len(dplrs) == 0:
                        break
                    n = 0
                    for dplr in dplrs:
                        n += 1
                        # default_code = self.get_product_default_code(line['product_id'][0])
                        if line['product_id'][0] == dplr['product_id']:
                            
                            tax_id = list(filter(lambda x: x['amount'] == dplr['iva'], tax_exento))[0]
                            price_subtotal_incl = (dplr['price'] + (dplr['price'] * tax_id['amount'] if tax_id else 0) / 100) * dplr['product_uom_qty']
                            product_dict = (0, 0, {
                                'full_product_name': dplr['product_name'],
                                # 'name': order_to_copy['name'],
                                'qty': dplr['product_uom_qty'],
                                # 'order_id': refund_order,
                                'product_id': dplr['product_id'],
                                'price_subtotal': dplr['price'] * dplr['product_uom_qty'],
                                'price_subtotal_incl': price_subtotal_incl,
                                'tax_ids': [(4, tax_id['id'])] if tax_id else False,
                                'taxes_ref': "{} %".format(dplr['iva'])
                            })
                            refund_lines.append(product_dict)
                            amount_total += price_subtotal_incl
                            taxes_total += abs(price_subtotal_incl) - abs(product_dict[2]['price_subtotal'])
                            # product_list_aux.append(dplrs[n - 1])
                            dplrs.pop(n - 1)

                if refund_lines:
                    order_to_copy.update({'lines': refund_lines, 'amount_total': amount_total, 'amount_tax': taxes_total})
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
                            'bancoPropio': dpr['banco_propio'],
                            })
                        dpr = {key: value for key, value in dpr.items()}
                        order_payment = tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'pos.make.payment', 'create', [data],
                                                        {'context': {'active_ids': [refund_order], 'active_id': refund_order}})
                        tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'pos.make.payment', 'check_payment', [[order_payment], dpr],
                                        {'context': {'active_ids': [refund_order], 'active_id': refund_order}})

                    #self.create_credit_pickings(tgt_info, refund_order)
                    errors.append(self.get_error(dhr, '200', '', refund_order))
            except Exception as errpropio:
                errmsg = errmsg + repr(errpropio)
                errors.append(self.get_error(dhr, "500", errmsg))
                print("Con error: {}".format(errmsg))
                pass

        if len(ncs_negative) > 0:
            for negative in ncs_negative:
                po_data.update({'dhrs': [negative[0]], 'dprs': negative[1], 'dplrs': negative[2]})
                self.create_pos_orders(tgt_info, po_data, True)


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
        domain = [[['id', '=', refund_order]]]
        po = tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'pos.order', 'search_read', domain,
                                {'fields': ['id', 'name', 'lines', 'picking_ids', 'session_id', 'branch_id', 'date_order']})[0]
        # picking_ids = picking_ids[0]['picking_ids'] if picking_ids else []
        for picking in picking_ids:
            params = [[picking['stock_picking_id']], picking['default_location_dest_id'],
                    po['lines'], picking['picking_type_id'], po['branch_id'], po['date_order']
                    ]
            tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'stock.picking', 'cpf_pol_custom_xmlrp', params)

        po = tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'pos.order', 'search_read', domain, {'fields': ['id', 'name', 'lines', 'picking_ids', 'session_id']})[0]
        picking_ids = po['picking_ids'] if picking_ids else []
        for picking in picking_ids:

            domain = [[['id', '=', picking]]]
            picking = tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'stock.picking', 'search_read', domain,
                                         {'fields': ['id', 'name', 'location_dest_id', 'move_ids_without_package', 'move_lines', 'date', 'branch_id']})
            for moves in picking:
                params = [[moves['id']], moves['move_ids_without_package'], moves['date'], 'stock_move', moves['branch_id'][0]]
                params1 = [[moves['id']], moves['move_ids_without_package'], moves['date'], 'stock_move']

                if moves['move_ids_without_package']:
                    tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'stock.picking', 'update_date_sml_2', params)
                    tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'stock.picking', 'change_create_date_sm_2', params1)
                params[1] = moves['move_lines']
                params1[1] = moves['move_lines']
                tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'stock.picking', 'update_date_sml_2', params)
                tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'stock.picking', 'change_create_date_sm_2', params1)

        tgt_rpc.execute_kw(tgt_db, tgt_uid, tgt_pwd, 'pos.order', 'action_pos_order_invoice_custom', [[refund_order]])

    @staticmethod
    def get_credit_dict(po, dhr):
        credit_dict = {
            'name': po['name'] + _(' REFUND'),
            'session_id': dhr['session_id'],
            'date_order': dhr['v_hora_pedido_time'],
            'pos_reference': po['pos_reference'],
            'lines': False,
            #'amount_tax': -po['amount_tax'],
            #'amount_total': -po['amount_total'],
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
            'v_tienda_caja_factura': "{}/{}".format(dhr['v_tienda'], dhr['v_cajafactura'])  , 
            'amount_return': 0,
        }

        return credit_dict

    def get_product_default_code(self, product_id):
        sql = """
            select pt.default_code 
            from product_product pp join product_template pt on (pt.id = pp.product_tmpl_id)
            where pp.id = {};
        """.format(product_id)
        product_info = self.server_url.getdata(sql, True, True)

        return product_info[0]['default_code']

    def get_po_valid(self):

        where = """ (dhr.fecha)::date = '{}'
                    and (dhr."valid" is null or not dhr."valid") 
                    and dhr.pos_order_id  is null 
                    and (dhr.sincro_state = 'draft' or dhr.sincro_state is null) 
                """.format(self.date_to_process)
        
        #where += "and v_cajafactura in ('6-86983', '5-82848')"

        sql = """
            with dhr as 
            (
                select dhr.*,  
                    (dhr.fecha)::date fecha_vta, 
                    (dhr.fecha)::date::text || ' ' || substring(dhr.v_hora_pedido::text from 12) hora_vta,
                    to_timestamp((dhr.fecha)::date::text || ' ' || substring(dhr.v_hora_pedido::text from 12), 'YYYY-MM-DD HH24:MI:SS') + interval '4 hour' v_hora_pedido_time,
                    to_timestamp((dhr.fecha)::date::text || ' ' || '00:00:00', 'YYYY-MM-DD HH24:MI:SS') v_date_min,
                    to_timestamp((dhr.fecha)::date::text || ' ' || '23:59:59', 'YYYY-MM-DD HH24:MI:SS') v_date_max,
                    rb.id branch_id, rp.identification_id, 
                    rp.id emp_id, rp."name" emp_name, ru.id user_id, ru.login,
                    rpc.id ci_cliente_id
                from data_header_retail dhr
                        join res_company rc on (rc.id = dhr.company_id) 
                        join res_branch rb on (rb.telephone = dhr.v_tienda) 
                        join res_partner rp on (rp.identification_id = dhr.v_cajeracedula and rp.active)
                        left join res_partner rpc on (rpc.identification_id = dhr.ci_cliente and rpc.active)                
                        join res_users ru on (ru.partner_id = rp.id and ru.active)
                where {}            
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
                                and ps.state in ('opened')
                                and (ps.closed_on_retail is null or not ps.closed_on_retail)
                                and ps.user_id  = dhr.user_id
                                and ps.start_at between dhr.v_date_min and dhr.v_date_max
                                )
            order by dhr.id;
        """.format(where)

        dhr = self.server_url.getdata(sql, True)
        print(dhr)

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
            select dplr.product_id prod_ref, dplr.product_uom_qty, dplr.price, dplr.iva,
                pp.id product_id, pp.product_tmpl_id, pt."name" product_name
            from data_header_retail dhr
                join data_product_lines_retail dplr on (dplr.v_tienda = dhr.v_tienda and dplr.v_cajafactura = dhr.v_cajafactura)
                left join product_product pp on (pp.default_code = dplr.product_id)
                left join product_template pt on (pt.id = pp.product_tmpl_id)
            where  dhr.id = {};
        """.format(idpo)
        dplr = self.server_url.getdata(sql, True, topythondict)


        return dpr, dplr

    def get_po_wrongamount(self):
        
      
        sql = """
            with payments as 
            (
                select  dhr.id, dpr.v_tienda, dpr.v_cajafactura, dhr.v_igtf,
                        sum(case when ppm.dolar_active then dpr.amount * dhr.rate else dpr.amount end) amount ,
                        sum(case when ppm.dolar_active then (dpr.amount * dhr.rate) / 1.03 else dpr.amount end) no_igtf_calc 			
                from data_payment_retail dpr 
                    join data_header_retail dhr on (dhr.v_cajafactura = dpr.v_cajafactura and dhr.v_tienda = dpr.v_tienda)
                    join pos_payment_method ppm on (dpr.code = ppm.payment_code)
                where (dhr."valid" is null or dhr."valid" = false) and dhr.pos_order_id  is null
                group by 1,2, 3, 4
            )
            select payments.id, payments.v_tienda, payments.v_cajafactura, payments.amount, payments.v_igtf,
                    sum( (product_uom_qty * price) * (1 + (iva/100)) ) ticket_total,
                    sum( ((product_uom_qty * price) * (1 + (iva/100)) ) ) + payments.v_igtf tick_w_igtf
            from data_product_lines_retail dplr 
                join payments on (dplr.v_cajafactura = payments.v_cajafactura and dplr.v_tienda = payments.v_tienda)
            group by 1, 2, 3, payments.amount, payments.v_igtf having abs( sum( ((product_uom_qty * price) * (1 + (iva/100)) ) ) + payments.v_igtf - payments.amount) > 1
            order by payments.id;      
        """
        wrong_amount = self.server_url.getdata(sql)

        return wrong_amount


    def get_error(self, dhr, status, errmsg, remote_id=False, error=False):

        if not error and dhr:
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
        elif dhr and 'id' in dhr.keys():
            self.updatedhr(False, dhr['id'])

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
                    missing += f"RI: [{product['prod_ref']}], "
                if not product["product_uom_qty"]:
                    missing += "Cantidad, "
                if not product["price"]:
                    missing += "Precio, "
                if product["iva"] is None:
                    missing += "I.V.A., "

        if missing != '':
            missing = missing[:len(missing) - 2]
            
        return missing

    
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
        #threaded_synchronization.run()
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
