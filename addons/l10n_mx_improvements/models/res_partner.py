# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta

class ResPartner(models.Model):
    _inherit = ['res.partner']

    l10n_mx_edi_usage = fields.Selection(
        selection=[
            ('G01', 'Adquisición de mercancías'),
            ('G02', 'Devoluciones, descuentos o bonos'),
            ('G03', 'Gastos en general'),
            ('I01', 'Construcciones'),
            ('I02', 'Mobilario y equipo de oficina por inversiones'),
            ('I03', 'Equipo de transporte'),
            ('I04', 'Equipo de cómputo y accesorios'),
            ('I05', 'Dados, troqueles, moldes, matrices y herramental'),
            ('I06', 'Comunicaciones telefónicas'),
            ('I07', 'Comunicaciones satelitales'),
            ('I08', 'Otra maquinaria y equipo'),
            ('D01', 'Honorarios médicos, dentales y gastos hospitalarios.'),
            ('D02', 'Gastos médicos por incapacidad o discapacidad'),
            ('D03', 'Gastos funerales'),
            ('D04', 'Donativos'),
            ('D05', 'Intereses reales efectivamente pagados por créditos hipotecarios (casa habitación)'),
            ('D06', 'Aportaciones voluntarias al SAR'),
            ('D07', 'Primas por seguors de gastos médicos'),
            ('D08', 'Gastos de transportación escolar obligatoria'),
            ('D09', 'Depósitos en cuenta de ahorro, primas que tengan como base planes de pensiones.'),
            ('D10', 'Pagos por servicios educativos (colegiaturas)'),
            ('P01', 'Por definir (sólo CFDI 3.3)'),
            ('S01', "Sin efectos fiscales"),
        ],
        string="Uso",
        default='G01',
        help="Se utiliza en CFDI 3.3 y 4.0 para expresar el motivo principal de uso para el recepto de la factura. Este "
             "valor es definido por el cliente.\nNota: NO es causa de cancelación si el recepetor le da un uso diferente "
             "al especificado en la factura.")
        
    l10n_mx_edi_payment_method_id = fields.Many2one(
        comodel_name='l10n_mx_edi.payment.method',
        string="Forma de Pago",
        store=True,
        readonly=False,
        default=lambda self: self.env.ref('l10n_mx_edi.payment_method_otros', raise_if_not_found=False),
        help="Indica la forma de pago para la factura, las opcioens pueden ser: "
             "Efectivo, Cheque, Tarjeta de Crédito, etc. Dejar en blanco si no se conoce y el XML mostrara 'Por definir'."
             )
