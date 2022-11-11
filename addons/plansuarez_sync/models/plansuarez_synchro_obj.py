# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
import psycopg2, psycopg2.extras

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

class BaseSynchroServer(models.Model):
    """Class to store the information regarding server."""

    _name = "plansuarez.synchro.server"
    _description = "Synchronized server"

    name = fields.Char(
        string="Server name", 
        help="Type the name for this connection",
        required=True)
    server_url = fields.Char(
        string="Sever Address", 
        help="Type Server Url or IP Address to access",
        required=True)
    server_port = fields.Integer(
        string="Port", 
        help="Type the Server Port if is used", 
        default=8069)
    server_db = fields.Char(
        string="Server Database",
        help="Type the Database Name for this Server",
        required=True)
    login = fields.Char(
        string="UserName", 
        help="Type the User Name or Login to access the Server",
        required=True)
    password = fields.Char(
        string="Password",
        help="Type password assigned to the user",
        required=True)
    connection_type = fields.Selection(
            [('odoo', 'Odoo'),
             ('psql', 'PostgreSQL')
            ], 
            string='Connection Type', 
            help="Select what kind of Server is",
            default='odoo'
        )
    # obj_ids = fields.One2many(
    #     "plansuarez.synchro.obj", "server_id", "Models", ondelete="cascade"
    # )

    def get_conexion_psql(self, dict=False):
        sconexion =  "host='{}' port={} dbname='{}' user={} password='{}'".format(
                    self.server_url, self.server_port, self.server_db, 
                    self.login, self.password)

        cn = psycopg2.connect(sconexion)
        return cn
    
    def getdata(self, sql, dict=False, topythondict=False):

        cn = self.get_conexion_psql(dict)
        if dict:
            crs = cn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            crs = cn.cursor()
        crs.execute(sql)
        records = crs.fetchall()
        if dict and topythondict:
            records = [{k:v for k, v in rec.items()} for rec in records]
            records = self.clean_none_values(records)

        cn.close()
        return records

    def clean_none_values(self, datadict):
        for r in datadict:
            for k, v in r.items():
                if v is None:
                    r[k] = False
        return datadict 

    def updatedata(self, sql):

        cn = self.get_conexion_psql()
        crs = cn.cursor()
        res = crs.execute(sql)
        cn.commit()
        cn.close()
        return res


class BaseSynchroObj(models.Model):
    """Class to store the operations done by wizard."""

    _name = "plansuarez.synchro.obj"
    _description = "Register Class"
    _order = "sequence"

    name = fields.Char(required=True)
    domain = fields.Char(required=True, default="[]")
    server_id = fields.Many2one(
        "plansuarez.synchro.server", "Server", ondelete="cascade", required=True
    )
    #model_id = fields.Many2one("ir.model", "Object to synchronize")
    action = fields.Selection(
        [("s", "Sales"), ("i", "Inventory"), ("b", "Both")],
        string="Type",
        help="What would be created: Sales=Only Sales, I=Only Inventory, B=Sales & Inventory",
        required=True,
        default="b",
    )
    sequence = fields.Integer("Sequence")
    active = fields.Boolean(default=True)
    synchronize_date = fields.Datetime("Latest Synchronization", help="Date/Time of Syncronization start", readonly=True)
    synchronize_end = fields.Datetime(string="Finished at", help="Date/Time Syncronization ended", readonly=True)
    
    line_id = fields.One2many(
        "plansuarez.synchro.obj.line", "obj_id", "IDs Affected") #, ondelete="cascade"


    # avoid_ids = fields.One2many(
    #     "plansuarez.synchro.obj.line", "obj_id", "IDs  Not Sync.", ondelete="cascade",
    #     domain=[('statuscode', '>=', '400')]
    # )

    @api.model
    def get_ids(self, obj, dt, domain=None, action=None):
        result = []
        return result


class BaseSynchroObjAvoid(models.Model):
    """Class to avoid the base synchro object."""

    _name = "plansuarez.synchro.obj.avoid"
    _description = "Fields to synchronize"

    name = fields.Char("Source Field", required=True)
    target = fields.Char("Target Field", required=True)
    obj_id = fields.Many2one(
        "plansuarez.synchro.obj", "Object", required=True) #, ondelete="cascade"
    

class BaseSynchroObjLine(models.Model):
    """Class to store object line in base synchro."""

    _name = "plansuarez.synchro.obj.line"
    _description = "Synchronized instances"

    name = fields.Datetime(
        "Date", required=True, default=lambda self: fields.Datetime.now()
    )
    obj_id = fields.Many2one("plansuarez.synchro.obj", "Object")  #ondelete="cascade")
    local_id = fields.Integer("Local ID", readonly=True)
    remote_id = fields.Integer("Remote ID", readonly=True)

    v_identidad = fields.Char(
        string="Identity",
        help="Transaction's Identity"
        )

    v_fecha = fields.Char(
        string="Date",
        help="Transaction's Date/Time"
        )

    v_tienda = fields.Char(
        string="Store",
        help="Transaction's Store"
        )
    
    v_cajafactura = fields.Char(
        string="Box Invoice",
        help="Transaction's Box Invoice"
    )

    statuscode = fields.Selection(
        [
            ("200", "Caja abierta satisfactoriamente."),
            ("201", "Devolución hecha correctamente."),
            ("500", "Ha ocurrido un error: "),
            ("422", "Error en estructura de entrada, valores incorrectos: "),
            ("406", "Ya se encuentra una sesión activa."),
            ("407", "Orden existente: "),
            ("412", "No existe sesión activa: "),
            ("404", "No existe cliente con documento asignado: ")
        ]
    )

    errordetail = fields.Char(
        string="Detail",
        help="Transaction's error if any"
    )

