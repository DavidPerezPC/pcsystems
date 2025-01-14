# -*- coding: utf-8 -*-
# from odoo import http


# class SyncContpaq(http.Controller):
#     @http.route('/sync_contpaq/sync_contpaq', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/sync_contpaq/sync_contpaq/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('sync_contpaq.listing', {
#             'root': '/sync_contpaq/sync_contpaq',
#             'objects': http.request.env['sync_contpaq.sync_contpaq'].search([]),
#         })

#     @http.route('/sync_contpaq/sync_contpaq/objects/<model("sync_contpaq.sync_contpaq"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('sync_contpaq.object', {
#             'object': obj
#         })
