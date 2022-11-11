import xmlrpc.client as xc
import requests
import os
from time import sleep

# DB = os.environ['ODOO_PRD_DB']
DB = 'productionn_20221031'
# USERNAME = os.environ['ODOO_USER']
USERNAME = 'admin'
# PASSWORD = os.environ['ODOO_PWD_ACCESS']
PASSWORD = '724qQSq&'
# URL = os.environ['ODOO_HOST']
URL = 'http://172.17.0.64'

common = xc.ServerProxy(f"{URL}/xmlrpc/2/common", allow_none=True)
uid = common.authenticate(DB, USERNAME, PASSWORD, {})
models = xc.ServerProxy(f"{URL}/xmlrpc/2/object", allow_none=True)


def open_close_sessions():
    try:
        data_2_process = []
        op_cl_domain = [[['identification', '!=', False]]]
        open_close_data = models.execute_kw(DB, uid, PASSWORD, 'data.open.close.retail', 'search_read', op_cl_domain, {'fields': ['combined', 'status', 'identification', 'fund', 'tienda', 'identidad', 'abierta', 'cerrada', 'fecha', 'cant_orden'], 'order': 'id'})
        for data in open_close_data:
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
        final_data_2_process = {
            'data': data_2_process,
        }

        response = requests.post(f'{URL}/openPos', json=final_data_2_process)
        print(response.text)
            
    except Exception as err:
        print(str(err))
        sleep(10)
        open_close_sessions()
 

if __name__ == "__main__":
    open_close_sessions()
