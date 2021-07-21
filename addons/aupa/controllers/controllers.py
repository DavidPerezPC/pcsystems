# -*- coding: utf-8 -*-
# from odoo import http


# class Aupa(http.Controller):
#     @http.route('/aupa/aupa/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/aupa/aupa/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('aupa.listing', {
#             'root': '/aupa/aupa',
#             'objects': http.request.env['aupa.aupa'].search([]),
#         })

#     @http.route('/aupa/aupa/objects/<model("aupa.aupa"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('aupa.object', {
#             'object': obj
#         })
