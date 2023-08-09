# -*- coding: utf-8 -*-
# from odoo import http


# class Caprepa(http.Controller):
#     @http.route('/caprepa/caprepa', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/caprepa/caprepa/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('caprepa.listing', {
#             'root': '/caprepa/caprepa',
#             'objects': http.request.env['caprepa.caprepa'].search([]),
#         })

#     @http.route('/caprepa/caprepa/objects/<model("caprepa.caprepa"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('caprepa.object', {
#             'object': obj
#         })
