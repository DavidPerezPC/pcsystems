# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2013 OpenERP s.a. (<http://openerp.com>).
#
#    DME SOLUCIONES
#    Jorge Medina <alfonso.moreno@dmesoluciones.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime as dt, timedelta
#log
import logging
import csv
import base64
import io
_logger = logging.getLogger(__name__)

DATE_NAMES = {
    'enero-febrero': '01-01',
    'febrero-marzo': '02-01',
    'marzo-abril': '03-01',
    'abril-mayo': '04-01',
    'mayo-junio': '05-01',
    'junio-julio': '06-01',
    'julio-agosto': '07-01',
    'agosto-septiembre': '08-01',
    'septiembre-octubre': '09-01',
    'octubre-noviembre': '10-01',
    'noviembre-diciembre': '11-01',
    'diciembre-enero': '12-01',
              }

class ImportStampsWizard(models.TransientModel):
    _name = 'finkokstamps.import.wizard'
    _description = 'Stamps Import Wizard'

    def _get_default_year(self):
        cyear = dt.strftime(dt.now(), "%Y")
        return cyear
    
    year = fields.Selection(
        selection = [('2020', '2020'),
                     ('2021', '2021'),
                     ('2022', '2022'),
                     ('2023', '2023'),
                     ('2024', '2024'),
                     ('2025', '2025'),
                     ('2026', '2026'),
                     ('2027', '2027'),
                     ('2028', '2028'),
                     ('2029', '2029'),
                     ('2030', '2030'),
                     ('2031', '2031'),
                     ('2032', '2032'),
                     ('2033', '2033'),
                     ('2034', '2034'),
                    ],
        string='Year',
        default=lambda self: self._get_default_year(),
        help='Year of the file(s) to process',
        required=True,
    )

    file_ids = fields.Many2many(
        'ir.attachment', 
        'finkokstamps_import_wizard_attachment_rel',
        'wizar_id', 
        'attachment_id', 
        'File(s)',
        required=True
        )

    def import_finkokstamps(self):

        stamps = self.env['finkokstamps.stamps']
        vats = self.env['finkokstamps.vats']
        ids = []
        action = False

        for file in self.file_ids:

            lines = file.index_content.split("\n")
            cmes = file.name[file.name.find("-")+1:]
            cmes = cmes.replace(".csv","")
            for line in lines:
                line_split = line.split(",")
                vat = line_split[0]
                if vat == 'rfc':
                    continue
                vat_id = vats._get_id(vat)
                data = {
                    'name': vat,
                    'vat_id': vat_id,
                    'stamps': int(line_split[1]),
                    'canceled': int(line_split[2]),
                    'date': f"{self.year}-{DATE_NAMES[cmes]}",
                }
                id = stamps.create(data)
                ids.append(id.id)
        # if ids:
        #     action = self.env['ir.actions.actions']._for_xml_id('finkokstamps.action_finkokstamps_stamps')
        #     if len(ids) <= 1 :
        #         form_view = [(self.env.ref('finkokstamps.finkokstamps_stamps_form').id, 'form')]
        #         if 'views' in action:
        #             action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
        #         else:
        #             action['views'] = form_view
        #         action['res_id'] = ids[0]
        #     else:
        #         action['domain'] = [('id', 'in', ids),('move_type', '=', 'entry')]
        #     context = {
        #         'default_move_type': 'entry',
        #         'default_partner_id': self.partner_id.id,
        #     }
        #     action['context'] = context

        return action
        